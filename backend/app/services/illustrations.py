import asyncio
import logging
from typing import Optional

from app.config import get_settings
from app.schemas.lesson import LessonContent
from app.services.image_search import search_lesson_images, search_wikimedia_candidates
from app.services.image_vision_verify import verify_images_with_vision
from app.services.illustration_scoring import ImageCandidate, heuristic_shortlist, merge_candidates
from app.services.openverse_search import search_openverse_candidates
from app.services.storage import rehost_images_to_s3
from app.services.svg_illustrations import generate_lesson_svgs
from app.services.web_image_search import search_web_candidates
from app.services.yandex_ai import (
    generate_lesson_images,
    generate_visual_queries,
    verify_image_candidates,
)

settings = get_settings()
logger = logging.getLogger(__name__)


def _pick_final(
    approved: list[ImageCandidate],
    shortlist: list[ImageCandidate],
    max_count: int,
    vision_had_errors: bool,
) -> list[ImageCandidate]:
    """Choose final images: vision-approved first, then safe fallback."""
    if approved:
        return approved[:max_count]

    if not shortlist:
        return []

    # Vision unavailable or rate-limited — trust text-verified shortlist
    if vision_had_errors:
        logger.info(f"Vision errors — fallback to text shortlist ({len(shortlist)} candidates)")
        return shortlist[:max_count]

    # Vision rejected all — use best-scored from shortlist (still passed text LLM)
    logger.info("Vision rejected all — fallback to top text-shortlisted images")
    return shortlist[:max_count]


async def _hybrid_web_search(
    topic: str,
    grade: int,
    subject: str,
    content: LessonContent,
) -> list[str]:
    """
    Hybrid search with two-stage AI verification:
    1. Gather many candidates from DDGS + Wikimedia + Openverse
    2. Text-based LLM shortlist (up to 10)
    3. Vision LLM checks each image before adding (up to 3 approved)
    """
    pack = await generate_visual_queries(topic, grade, subject, content)
    max_count = settings.image_max_count
    shortlist_size = settings.image_vision_shortlist

    web_result, wiki_result, ov_result = await asyncio.gather(
        search_web_candidates(topic, grade, subject, pack.queries_ru),
        search_wikimedia_candidates(topic, subject, pack.queries_en, pack.visual_type),
        search_openverse_candidates(topic, subject, pack.queries_en),
        return_exceptions=True,
    )

    pools: list[list[ImageCandidate]] = []
    for label, result in (("web", web_result), ("wikimedia", wiki_result), ("openverse", ov_result)):
        if isinstance(result, Exception):
            logger.warning(f"{label} search failed: {result}")
            continue
        if result:
            pools.append(result)

    if not pools:
        logger.info(f"No image candidates for '{topic}'")
        return []

    pool = merge_candidates(pools)
    logger.info(f"Merged {len(pool)} candidates for '{topic}'")

    pool_dicts = [c.to_dict() for c in pool]

    # Stage 1: text-based shortlist
    indices = await verify_image_candidates(
        topic, grade, subject, content, pool_dicts, max_select=shortlist_size
    )

    if indices:
        shortlist = [pool[i] for i in indices if 0 <= i < len(pool)]
        logger.info(f"Text shortlist: {len(shortlist)} candidates for '{topic}'")
    else:
        shortlist = heuristic_shortlist(pool, max_count=shortlist_size)
        logger.info(f"Text verify empty — heuristic shortlist: {len(shortlist)} for '{topic}'")

    if not shortlist:
        logger.info(f"No shortlist for '{topic}'")
        return []

    # Stage 2: vision verify each candidate before adding
    approved: list[ImageCandidate] = []
    vision_errors = 0

    if settings.image_vision_verify and settings.groq_api_key:
        approved, vision_errors = await verify_images_with_vision(
            shortlist, topic, grade, subject, content, max_approve=max_count
        )

    selected = _pick_final(approved, shortlist, max_count, vision_errors > 0)

    if not selected:
        logger.info(f"No illustrations selected for '{topic}'")
        return []

    urls = [c.image_url for c in selected]
    logger.info(f"Final selection: {len(urls)} images for '{topic}'")
    return await rehost_images_to_s3(urls, topic)


async def get_lesson_illustrations(
    topic: str,
    grade: int,
    subject: str,
    content: Optional[LessonContent] = None,
) -> list[str]:
    """Route illustration generation to the configured provider."""
    provider = settings.image_provider.lower()

    if provider == "wikimedia":
        if not content:
            return []
        urls = await search_lesson_images(topic, grade, subject, content=content)
        return await rehost_images_to_s3(urls, topic)

    if provider == "yandexart":
        return await generate_lesson_images(topic, grade, subject)

    if provider == "ai_svg":
        if not content:
            return []
        return await generate_lesson_svgs(topic, grade, subject, content)

    if not content:
        logger.info(f"No lesson content for illustrations, skipping hybrid search for '{topic}'")
        return []

    return await _hybrid_web_search(topic, grade, subject, content)
