import io
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Chunk, Document
from app.services.embeddings import embedder
from app.services.retrieval import chunk_text
from app.services.storage import get_storage

logger = logging.getLogger("ingestion")
ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def extract_text(filename: str, data: bytes) -> str:
    if Path(filename).suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    return data.decode("utf-8", errors="replace")


def ingest_document(db: Session, document_id: int) -> None:
    """Idempotent: re-running replaces the document's chunks (safe for at-least-once delivery)."""
    doc = db.get(Document, document_id)
    if doc is None:
        return
    try:
        text = extract_text(doc.filename, get_storage().get(doc.storage_key))
        pieces = chunk_text(text)
        if not pieces:
            raise ValueError("no extractable text")
        doc.chunks.clear()
        doc.chunks.extend(
            Chunk(ordinal=i, content=piece, embedding=embedder.embed(f"{doc.title}\n{piece}"))
            for i, piece in enumerate(pieces)
        )
        doc.chunk_count, doc.status = len(pieces), "ready"
    except Exception:
        logger.exception("ingestion failed", extra={"extra_fields": {"document_id": document_id}})
        doc.status = "failed"
    db.commit()
