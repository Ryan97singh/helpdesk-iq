from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # Connection pooling sized for a single API pod; scale out with more pods, not bigger pools.
    return create_engine(url, pool_size=10, max_overflow=5, pool_pre_ping=True)


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  (register tables)

    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            # API workers and event workers boot concurrently: serialise DDL with an advisory lock.
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(4242)")
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        Base.metadata.create_all(conn)
        if conn.dialect.name == "postgresql":
            # Approximate-nearest-neighbour index: sub-linear vector search as the corpus grows.
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)"
            )
