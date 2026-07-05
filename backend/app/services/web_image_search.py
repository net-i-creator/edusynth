import asyncio
import logging
from typing import Optional

from app.config import get_settings
from app.schemas.lesson import LessonContent
from app.services.illustration_scoring import ImageCandidate, score_candidate

logger = logging.getLogger(__name__)
settings = get_settings()

MIN_WIDTH = 400
MIN_HEIGHT = 250


def _build_fallback_queries_ru(topic: str, grade: int, subject: str) -> list[str]:
    return [
        f"{topic} наглядно иллюстрация {grade} класс",
        f"{topic} рисунок {subject}",
        f"{topic} чертёж {grade} класс",
    ]


def _search_images_sync(query: str, max_results: int = 10) -> list[dict]:
    from ddgs import DDGS

    with DDGS() as ddgs:
        return list(ddgs.images(query, region="ru-ru", max_results=max_results))


async def _search_images(query: str, max_results: int = 10) -> list[dict]:
    for attempt in range(3):
        try:
            return await asyncio.to_thread(_search_images_sync, query, max_results)
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2 + attempt * 2)
                continue
            logger.warning(f"Image search failed for '{query}': {e}")
            return []
    return []


async def search_web_candidates(
    topic: str,
    grade: int,
    subject: str,
    queries_ru: list[str],
) -> list[ImageCandidate]:
    """Search DDGS/Bing for Russian educational illustrations."""
    queries = queries_ru[:5] if queries_ru else _build_fallback_queries_ru(topic, grade, subject)

    logger.info(f"Web image search queries: {queries}")

    pool: list[ImageCandidate] = []
    seen: set[str] = set()
    candidate_pool = settings.image_candidate_pool

    for query in queries:
        results = await _search_images(query, max_results=12)
        for r in results:
            image_url = r.get("image") or ""
            if not image_url or image_url in seen:
                continue
            seen.add(image_url)

            try:
                width = int(r.get("width") or 0)
                height = int(r.get("height") or 0)
            except (TypeError, ValueError):
                width, height = 0, 0

            if width and width < MIN_WIDTH:
                continue
            if height and height < MIN_HEIGHT:
                continue

            title = r.get("title") or ""
            page_url = r.get("url") or ""
            heuristic = score_candidate(
                title, page_url, image_url, topic, subject, width, height
            )
            if heuristic < 0:
                continue

            pool.append(ImageCandidate(
                image_url=image_url,
                title=title,
                page_url=page_url,
                source="web",
                heuristic_score=heuristic,
            ))

        if len(pool) >= candidate_pool:
            break

    pool.sort(key=lambda x: x.heuristic_score, reverse=True)
    return pool[:candidate_pool]


async def search_web_images(
    topic: str,
    grade: int,
    subject: str,
    content: Optional[LessonContent] = None,
) -> list[str]:
    """Legacy standalone web search — used by wikimedia-only fallback paths."""
    from app.services.yandex_ai import generate_visual_queries

    if content:
        pack = await generate_visual_queries(topic, grade, subject, content)
        queries = pack.queries_ru
    else:
        queries = _build_fallback_queries_ru(topic, grade, subject)

    candidates = await search_web_candidates(topic, grade, subject, queries)
    return [c.image_url for c in candidates[: settings.image_max_count]]
