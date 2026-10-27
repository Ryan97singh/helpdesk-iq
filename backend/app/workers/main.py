"""Standalone event worker: `python -m app.workers.main`.

Consumes the Redis Stream with a consumer group, so N worker replicas share the load and each
event is processed by exactly one of them. Failed events are retried (left pending, reclaimed after
an idle timeout) up to MAX_DELIVERIES, then moved to a dead-letter stream for inspection.
"""

import json
import logging
import os
import socket

import redis
from prometheus_client import start_http_server

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db import init_db
from app.services.events import DEAD_LETTER, STREAM
from app.workers.handlers import dispatch

GROUP = "helpdesk-workers"
MAX_DELIVERIES = 3
RECLAIM_IDLE_MS = 60_000
logger = logging.getLogger("worker")


def handle(r: redis.Redis, msg_id: str, fields: dict) -> None:
    try:
        dispatch(fields["type"], json.loads(fields["data"]))
        r.xack(STREAM, GROUP, msg_id)
    except Exception:
        info = r.xpending_range(STREAM, GROUP, min=msg_id, max=msg_id, count=1)
        deliveries = info[0]["times_delivered"] if info else 1
        logger.exception("event failed", extra={"extra_fields": {"id": msg_id, "deliveries": deliveries}})
        if deliveries >= MAX_DELIVERIES:
            r.xadd(DEAD_LETTER, {**fields, "original_id": msg_id})
            r.xack(STREAM, GROUP, msg_id)


def main() -> None:
    setup_logging()
    init_db()
    start_http_server(int(os.getenv("WORKER_METRICS_PORT", "9100")))
    r = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise
    consumer = f"{socket.gethostname()}-{os.getpid()}"
    logger.info("worker started", extra={"extra_fields": {"consumer": consumer}})
    while True:
        # Reclaim messages another (possibly crashed) consumer left pending for too long.
        _, claimed, _ = r.xautoclaim(STREAM, GROUP, consumer, min_idle_time=RECLAIM_IDLE_MS, count=10)
        for msg_id, fields in claimed:
            handle(r, msg_id, fields)
        for _, messages in r.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=10, block=5000) or []:
            for msg_id, fields in messages:
                handle(r, msg_id, fields)


if __name__ == "__main__":
    main()
