import logging

from fastapi import HTTPException

from app.config import get_settings
from app.services.cache import _get_redis

settings = get_settings()
logger = logging.getLogger(__name__)

GUEST_KEY_PREFIX = "guest_gen:"
GUEST_TTL_SECONDS = 60 * 60 * 24 * 365  # 1 year


async def get_guest_generation_count(guest_id: str) -> int:
    client = _get_redis()
    if not client or not guest_id:
        return 0
    try:
        val = await client.get(f"{GUEST_KEY_PREFIX}{guest_id}")
        return int(val) if val else 0
    except Exception as e:
        logger.warning("Guest limit read failed: %s", e)
        return 0


async def check_guest_can_generate(guest_id: str) -> None:
    """Raise 403 if anonymous guest exceeded free generation limit."""
    count = await get_guest_generation_count(guest_id)
    if count >= settings.guest_lesson_limit:
        raise HTTPException(
            status_code=403,
            detail="Guest limit reached. Please register to continue generating lessons.",
        )


async def record_guest_generation(guest_id: str) -> None:
    client = _get_redis()
    if not client or not guest_id:
        return
    try:
        key = f"{GUEST_KEY_PREFIX}{guest_id}"
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, GUEST_TTL_SECONDS)
        await pipe.execute()
    except Exception as e:
        logger.warning("Guest limit write failed: %s", e)
