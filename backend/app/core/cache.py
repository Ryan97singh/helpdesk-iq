"""Cache abstraction: Redis in docker-compose / AWS (ElastiCache), in-memory for local dev and tests."""

import threading
import time
from abc import ABC, abstractmethod
from functools import lru_cache

from app.core.config import get_settings


class Cache(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None: ...

    @abstractmethod
    def set(self, key: str, value: str, ttl: int) -> None: ...

    @abstractmethod
    def incr(self, key: str, ttl: int) -> int:
        """Atomically increment a counter, starting a TTL window on first use."""

    @abstractmethod
    def ping(self) -> bool: ...


class InMemoryCache(Cache):
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def _alive(self, key: str) -> tuple[str, float] | None:
        item = self._data.get(key)
        if item and item[1] < time.monotonic():
            self._data.pop(key, None)
            return None
        return item

    def get(self, key: str) -> str | None:
        with self._lock:
            item = self._alive(key)
            return item[0] if item else None

    def set(self, key: str, value: str, ttl: int) -> None:
        with self._lock:
            self._data[key] = (value, time.monotonic() + ttl)

    def incr(self, key: str, ttl: int) -> int:
        with self._lock:
            item = self._alive(key)
            count = int(item[0]) + 1 if item else 1
            expiry = item[1] if item else time.monotonic() + ttl
            self._data[key] = (str(count), expiry)
            return count

    def ping(self) -> bool:
        return True

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class RedisCache(Cache):
    def __init__(self, url: str) -> None:
        import redis

        self._r = redis.Redis.from_url(url, decode_responses=True)

    def get(self, key: str) -> str | None:
        return self._r.get(key)

    def set(self, key: str, value: str, ttl: int) -> None:
        self._r.set(key, value, ex=ttl)

    def incr(self, key: str, ttl: int) -> int:
        pipe = self._r.pipeline()
        pipe.incr(key)
        pipe.expire(key, ttl, nx=True)
        return int(pipe.execute()[0])

    def ping(self) -> bool:
        try:
            return bool(self._r.ping())
        except Exception:
            return False


@lru_cache
def get_cache() -> Cache:
    url = get_settings().redis_url
    return RedisCache(url) if url else InMemoryCache()
