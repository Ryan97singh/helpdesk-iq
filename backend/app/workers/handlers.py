import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.metrics import EVENTS
from app.db import SessionLocal
from app.services.ingestion import ingest_document
from app.services.triage import triage_ticket

logger = logging.getLogger("worker")

HANDLERS: dict[str, Callable[[Session, dict], None]] = {
    "document.uploaded": lambda db, d: ingest_document(db, d["document_id"]),
    "ticket.created": lambda db, d: triage_ticket(db, d["ticket_id"]),
}


def dispatch(event_type: str, data: dict) -> None:
    handler = HANDLERS.get(event_type)
    if handler is None:
        logger.warning("no handler for event", extra={"extra_fields": {"type": event_type}})
        return
    with SessionLocal() as db:
        try:
            handler(db, data)
        except Exception:
            EVENTS.labels(event_type, "error").inc()
            raise
    EVENTS.labels(event_type, "ok").inc()
