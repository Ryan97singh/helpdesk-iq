"""Chat transcripts (Repository pattern).

Transcripts are append-heavy, schemaless-ish documents with per-message metadata (sources, tokens),
so they live in MongoDB in docker-compose (DynamoDB on AWS: PK=user_id, SK=timestamp). Locally an
in-memory implementation keeps the app dependency-free. Callers only see the interface.
"""

import threading
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import lru_cache

from app.core.config import get_settings


class ConversationRepository(ABC):
    @abstractmethod
    def append(self, user_id: int, role: str, content: str, meta: dict | None = None) -> None: ...

    @abstractmethod
    def recent(self, user_id: int, limit: int = 20) -> list[dict]:
        """Most recent messages, oldest first."""

    @abstractmethod
    def clear(self, user_id: int) -> None: ...


def _doc(user_id: int, role: str, content: str, meta: dict | None) -> dict:
    return {"user_id": user_id, "role": role, "content": content, "meta": meta or {},
            "created_at": datetime.now(UTC).isoformat()}


class InMemoryConversationRepository(ConversationRepository):
    def __init__(self) -> None:
        self._data: dict[int, list[dict]] = {}
        self._lock = threading.Lock()

    def append(self, user_id, role, content, meta=None):
        with self._lock:
            self._data.setdefault(user_id, []).append(_doc(user_id, role, content, meta))

    def recent(self, user_id, limit=20):
        with self._lock:
            return list(self._data.get(user_id, [])[-limit:])

    def clear(self, user_id):
        with self._lock:
            self._data.pop(user_id, None)


class MongoConversationRepository(ConversationRepository):
    def __init__(self, url: str) -> None:
        from pymongo import ASCENDING, DESCENDING, MongoClient

        self.col = MongoClient(url, serverSelectionTimeoutMS=3000)["helpdeskiq"]["messages"]
        self.col.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        self._desc = DESCENDING

    def append(self, user_id, role, content, meta=None):
        self.col.insert_one(_doc(user_id, role, content, meta))

    def recent(self, user_id, limit=20):
        docs = list(self.col.find({"user_id": user_id}, {"_id": 0}).sort("created_at", self._desc).limit(limit))
        return docs[::-1]

    def clear(self, user_id):
        self.col.delete_many({"user_id": user_id})


@lru_cache
def get_conversations() -> ConversationRepository:
    url = get_settings().mongo_url
    return MongoConversationRepository(url) if url else InMemoryConversationRepository()
