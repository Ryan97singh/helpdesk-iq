"""Chunking + vector search. PostgreSQL uses pgvector's cosine-distance operator (HNSW index);
SQLite falls back to an in-Python scan, which is fine for a local demo-sized corpus."""

import re
from dataclasses import dataclass

from pgvector.sqlalchemy import Vector
from sqlalchemy import cast, select
from sqlalchemy.orm import Session

from app.models import EMBED_DIM, Chunk, Document
from app.services.embeddings import cosine, embedder, tokenize


@dataclass
class Hit:
    chunk_id: int
    document_id: int
    document_title: str
    content: str
    score: float


def chunk_text(text: str, max_chars: int = 600, overlap: int = 100) -> list[str]:
    """Paragraph-aware chunking with overlap so an answer spanning a boundary is still retrievable."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current)
            tail = current[-overlap:]
            current = tail[tail.find(" ") + 1:] + "\n\n" + para  # start the overlap on a word boundary
        else:
            current = f"{current}\n\n{para}" if current else para
        while len(current) > max_chars:  # a single huge paragraph
            chunks.append(current[:max_chars])
            current = current[max_chars - overlap:]
    if current:
        chunks.append(current)
    return chunks


def keyword_score(query_terms: set[str], text: str) -> float:
    """Fraction of the query's terms present in the chunk (a lightweight lexical signal)."""
    if not query_terms:
        return 0.0
    return len(query_terms & set(tokenize(text))) / len(query_terms)


def search(db: Session, query: str, k: int = 4, min_score: float = 0.25) -> list[Hit]:
    """Hybrid retrieval: vector similarity recalls candidates, keyword overlap reranks them.
    Dense vectors catch paraphrases; exact terms (product names, "VPN", "PAN") keep precision."""
    qvec = embedder.embed(query)
    candidates = k * 3
    if db.get_bind().dialect.name == "postgresql":
        # The column is a JSON/Vector variant; cast so SQLAlchemy uses pgvector's comparator (`<=>`).
        distance = cast(Chunk.embedding, Vector(EMBED_DIM)).cosine_distance(qvec)
        rows = db.execute(
            select(Chunk, Document.title, (1 - distance).label("score"))
            .join(Document)
            .where(Document.status == "ready")
            .order_by(distance)
            .limit(candidates)
        ).all()
        hits = [Hit(c.id, c.document_id, title, c.content, float(score)) for c, title, score in rows]
    else:
        rows = db.execute(select(Chunk, Document.title).join(Document).where(Document.status == "ready")).all()
        hits = sorted(
            (Hit(c.id, c.document_id, title, c.content, cosine(qvec, c.embedding)) for c, title in rows),
            key=lambda h: h.score,
            reverse=True,
        )[:candidates]

    terms = set(tokenize(query))
    for h in hits:
        h.score = 0.5 * max(h.score, 0.0) + 0.5 * keyword_score(terms, f"{h.document_title} {h.content}")
    hits.sort(key=lambda h: h.score, reverse=True)
    return [h for h in hits[:k] if h.score >= min_score]
