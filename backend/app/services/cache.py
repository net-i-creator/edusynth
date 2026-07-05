import json
import hashlib
import logging
from uuid import UUID

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis | None:
    global _redis_client
    if _redis_client is None and settings.redis_url:
        try:
            _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        except Exception as e:
            logger.warning("Redis unavailable, caching disabled: %s", e)
    return _redis_client


def generate_topic_hash(topic: str, grade: int, subject: str) -> str:
    raw = f"{topic.strip().lower()}:{grade}:{subject.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def get_cached_lesson(topic_hash: str) -> dict | None:
    client = _get_redis()
    if not client:
        return None
    try:
        data = await client.get(f"lesson:{topic_hash}")
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning("Redis read failed: %s", e)
    return None


async def cache_lesson(topic_hash: str, lesson_data: dict) -> None:
    client = _get_redis()
    if not client:
        return
    try:
        await client.set(
            f"lesson:{topic_hash}",
            json.dumps(lesson_data, ensure_ascii=False, default=str),
            ex=settings.cache_ttl,
        )
    except Exception as e:
        logger.warning("Redis write failed: %s", e)


async def cache_user_session(user_id: UUID, token: str) -> None:
    client = _get_redis()
    if not client:
        return
    try:
        await client.set(
            f"session:{user_id}",
            token,
            ex=settings.access_token_expire_minutes * 60,
        )
    except Exception as e:
        logger.warning("Redis session write failed: %s", e)


async def get_cached_session(user_id: UUID) -> str | None:
    client = _get_redis()
    if not client:
        return None
    try:
        return await client.get(f"session:{user_id}")
    except Exception as e:
        logger.warning("Redis session read failed: %s", e)
        return None


async def invalidate_session(user_id: UUID) -> None:
    client = _get_redis()
    if not client:
        return
    try:
        await client.delete(f"session:{user_id}")
    except Exception as e:
        logger.warning("Redis session delete failed: %s", e)
