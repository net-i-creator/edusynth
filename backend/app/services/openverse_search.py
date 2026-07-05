import logging

import httpx

from app.config import get_settings
from app.services.illustration_scoring import ImageCandidate, score_candidate

logger = logging.getLogger(__name__)
settings = get_settings()

OPENVERSE_API = "https://api.openverse.org/v1/images/"
MIN_WIDTH = 400

USER_AGENT = "Umbaza/1.0 (educational lesson generator; contact@umbaza.ru)"


async def search_openverse_candidates(
    topic: str,
    subject: str,
    queries_en: list[str],
) -> list[ImageCandidate]:
    """Search Openverse for CC-licensed educational illustrations."""
    queries = queries_en[:3]
    if not queries:
        return []

    logger.info(f"Openverse search queries: {queries}")

    pool: list[ImageCandidate] = []
    seen: set[str] = set()
    candidate_pool = max(10, settings.image_candidate_pool // 2)

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        for query in queries:
            params = {
                "q": query,
                "page_size": 10,
                "license": "cc0,by,by-sa",
            }
            try:
                response = await client.get(OPENVERSE_API, params=params)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                logger.warning(f"Openverse search failed for '{query}': {e}")
                continue

            for item in data.get("results", []):
                image_url = item.get("url") or ""
                if not image_url or image_url in seen:
                    continue

                width = item.get("width") or 0
                if width and width < MIN_WIDTH:
                    continue

                seen.add(image_url)
                title = item.get("title") or item.get("alt_text") or query
                page_url = item.get("foreign_landing_url") or item.get("creator_url") or ""

                heuristic = score_candidate(
                    title, page_url, image_url, topic, subject, width, item.get("height") or 0
                )
                if heuristic < 0:
                    continue

                pool.append(ImageCandidate(
                    image_url=image_url,
                    title=title,
                    page_url=page_url,
                    source="openverse",
                    heuristic_score=heuristic,
                ))

            if len(pool) >= candidate_pool:
                break

    pool.sort(key=lambda x: x.heuristic_score, reverse=True)
    return pool[:candidate_pool]
