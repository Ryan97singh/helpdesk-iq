"""Event bus (publish/subscribe) decoupling slow work (document ingestion, AI triage) from requests.

* Redis Streams + consumer group when REDIS_URL is set; a separate worker process consumes
  (`python -m app.workers.main`). On AWS the same contract maps to SQS -> Lambda / ECS worker.
* Otherwise a background thread in the API process consumes an in-memory queue.
* EVENTS_SYNC=true dispatches inline (deterministic tests).
"""

import json
import logging
import queue
import threading
from abc import ABC, abstractmethod
from functools import lru_cache

from app.core.config import get_settings

logger = logging.getLogger("events")
STREAM = "helpdesk.events"
DEAD_LETTER = "helpdesk.events.dlq"


class EventBus(ABC):
    @abstractmethod
    def publish(self, event_type: str, data: dict) -> None: ...


class InProcessEventBus(EventBus):
    def __init__(self, sync: bool = False) -> None:
        self.sync = sync
        self._q: queue.Queue[tuple[str, dict]] = queue.Queue()
        self._thread: threading.Thread | None = None

    def publish(self, event_type: str, data: dict) -> None:
        from app.workers.handlers import dispatch

        if self.sync:
            dispatch(event_type, data)
            return
        self._ensure_worker()
        self._q.put((event_type, data))

    def _ensure_worker(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="event-worker", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        from app.workers.handlers import dispatch

        while True:
            event_type, data = self._q.get()
            try:
                dispatch(event_type, data)
            except Exception:
                logger.exception("event handler failed", extra={"extra_fields": {"type": event_type}})
            finally:
                self._q.task_done()

    def drain(self) -> None:
        self._q.join()


class RedisStreamEventBus(EventBus):
    def __init__(self, url: str) -> None:
        import redis

        self.r = redis.Redis.from_url(url, decode_responses=True)

    def publish(self, event_type: str, data: dict) -> None:
        self.r.xadd(STREAM, {"type": event_type, "data": json.dumps(data)}, maxlen=100_000, approximate=True)


@lru_cache
def get_event_bus() -> EventBus:
    s = get_settings()
    if s.redis_url and not s.events_sync:
        return RedisStreamEventBus(s.redis_url)
    return InProcessEventBus(sync=s.events_sync)
