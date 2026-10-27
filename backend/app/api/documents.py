from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.security import CurrentUser, DbSession, require_roles
from app.models import Document, Role, User
from app.schemas import DocumentOut
from app.services.events import get_event_bus
from app.services.ingestion import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES
from app.services.storage import get_storage

router = APIRouter(prefix="/api/documents", tags=["documents"])
Editor = Annotated[User, Depends(require_roles(Role.admin, Role.agent))]


def _default_title(filename: str, data: bytes) -> str:
    """Markdown's first heading if present, otherwise a humanised file name."""
    if filename.lower().endswith(".md"):
        first = data[:500].decode("utf-8", errors="ignore").lstrip().splitlines()[:1]
        if first and first[0].startswith("# "):
            return first[0][2:]
    return Path(filename).stem.replace("_", " ").replace("-", " ").title()


@router.get("", response_model=list[DocumentOut])
def list_documents(_: CurrentUser, db: DbSession):
    return db.scalars(select(Document).order_by(Document.created_at.desc())).all()


@router.post("", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
def upload_document(user: Editor, db: DbSession, file: UploadFile = File(...), title: str | None = Form(None)):
    s = get_settings()
    if s.demo_mode and (db.scalar(select(func.count(Document.id))) or 0) >= s.demo_max_documents:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The public demo's knowledge base is full")
    filename = file.filename or "upload.txt"
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF, Markdown and text files are supported")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)  # sync route: FastAPI runs it in the threadpool
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds 10 MB")
    if not data.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")
    key = get_storage().put(filename, data)
    doc = Document(title=(title or _default_title(filename, data)).strip()[:255], filename=filename,
                   storage_key=key, uploaded_by=user.id)
    db.add(doc)
    db.commit()
    # 202 Accepted: parsing + embedding happen asynchronously in the worker.
    get_event_bus().publish("document.uploaded", {"document_id": doc.id})
    db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, _: Annotated[User, Depends(require_roles(Role.admin))], db: DbSession):
    if get_settings().demo_mode:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Deleting documents is disabled in the public demo")
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    get_storage().delete(doc.storage_key)
    db.delete(doc)
    db.commit()
