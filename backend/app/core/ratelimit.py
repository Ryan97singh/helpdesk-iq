import time

from fastapi import HTTPException, status

from app.core.cache import get_cache
from app.core.config import get_settings
from app.core.security import CurrentUser


def rate_limit(user: CurrentUser) -> None:
    """Fixed-window per-user limit on LLM-backed endpoints: protects spend as much as availability."""
    limit = get_settings().rate_limit_per_minute
    window = int(time.time() // 60)
    count = get_cache().incr(f"rl:{user.id}:{window}", ttl=60)
    if count > limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Rate limit exceeded, try again in a minute",
            headers={"Retry-After": "60"},
        )
