from redis.asyncio import Redis
from app.core.config import settings
from functools import lru_cache

@lru_cache(maxsize=1)
def get_redis() -> Redis | None:
    if not settings.REDIS_URL:
        return None
    return Redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)