import logging
import re
from typing import Optional

import httpx

from app.schemas.lesson import LessonContent
from app.services.illustration_scoring import ImageCandidate
from app.services.yandex_ai import generate_image_search_queries, generate_visual_queries

logger = logging.getLogger(__name__)

WIKIMEDIA_API = "https://commons.wikimedia.org/w/api.php"
MAX_IMAGES = 3
MIN_WIDTH = 400
THUMB_WIDTH = 800
MIN_ABSOLUTE_SCORE = 50
MIN_ABSOLUTE_SCORE_GENERAL = 35

BLOCKLIST = (
    "manuscript", "pulsar", "astronomy", "cosmos", "space", "dynkin",
    "vintage", "antique", "ancient", "historical", "telescope", "galaxy",
    "nebula", "planet", "orbit", "satellite", "kepler", "caterpillar",
    "morphology", "butterfly", "insect", "anatomy", "medical", "virus",
    "map_of", "flag_of", "portrait", "photo_of", "building", "church",
    "puzzle", "bird", "tiling", "projector", "pinhole", "hyperbola",
    "linkage", "centrode", "solid angle", "wind-from", "aircraft", "drift",
    "venn", "classification", "leipzig", "anomal", "refraction", "gazette",
    "engineer", "architect", "gif", "rocker", "parallelogramlinkage",
    "camera", "focal", "crop factor", "octeract", "cognitive", "bias",
    "bastilhado", "obscure-female", "euro-construction", "palanca",
    "soudure", "projection force", "petrie", "polytope", "tesseract", "mercator",
)

SIMPLE_BOOST = (
    "simple", "basic", "elementary", "orisymbol", "labeled", "sketch",
)

PHRASE_BOOST = (
    ("equal angles", 35),
    ("vertical angles", 35),
    ("vertical angle", 30),
    ("similar triangles", 40),
    ("similar triangle", 35),
    ("intersecting lines", 25),
    ("line diagram", 20),
    ("fraction pie", 40),
    ("fraction circle", 40),
    ("pie chart", 30),
    ("number line", 25),
)

PREFER_KEYWORDS = (
    "diagram", "triangle", "triangles", "angle", "angles", "similar",
    "geometry", "illustration", "figure", "drawing", "proportional",
    "fraction", "fractions", "chart",
)

QUERY_STOP_WORDS = frozenset({
    "school", "textbook", "simple", "illustration", "educational",
    "drawing", "diagram", "grade", "geometry", "mathematics", "the",
    "and", "for", "with", "from", "two", "corresponding", "line", "basic", "svg",
})

GEOMETRY_SUBJECTS = frozenset({"Геометрия"})
MATH_SUBJECTS = frozenset({"Математика", "Алгебра", "Геометрия"})

USER_AGENT = "Umbaza/1.0 (educational lesson generator; contact@umbaza.ru)"


def _score_image(title: str, mime: str, query_words: Optional[set[str]] = None) -> int:
    t = title.lower()

    for kw in BLOCKLIST:
        if kw in t:
            return -1000

    score = 0

    for phrase, boost in PHRASE_BOOST:
        if phrase in t:
            score += boost

    for kw in SIMPLE_BOOST:
        if kw in t:
            score += 15

    for kw in PREFER_KEYWORDS:
        if kw in t:
            score += 10

    if t.endswith(".svg") or mime == "image/svg+xml":
        score += 35
    elif mime in ("image/jpeg", "image/png") and "similar" in t:
        score += 10
    elif mime == "image/jpeg":
        score -= 10

    if t.endswith(".gif"):
        return -1000

    clean = re.sub(r"^file:", "", t)
    if len(clean) > 65:
        score -= 20

    if query_words:
        score += sum(10 for w in query_words if len(w) > 3 and w in t)

    return score


def _extract_key_terms(queries: list[str]) -> list[str]:
    terms: list[str] = []
    for q in queries:
        for w in q.lower().split():
            if w not in QUERY_STOP_WORDS and len(w) > 3 and w not in terms:
                terms.append(w)
    return terms[:6]


def _build_short_queries(
    ai_queries: list[str],
    topic: str,
    visual_type: str = "illustration",
) -> list[str]:
    """Build short Wikimedia-friendly queries (2-3 words + diagram)."""
    short: list[str] = []
    topic_l = topic.lower()
    terms = _extract_key_terms(ai_queries)

    if "дроб" in topic_l or "fraction" in " ".join(ai_queries).lower():
        short.extend([
            "fraction pie chart diagram",
            "fraction circle diagram",
            "fraction number line",
        ])
    if "треугольник" in topic_l and "подоб" in topic_l:
        short.extend(["similar triangles diagram", "AA similar triangles"])
    elif "вертикальн" in topic_l:
        short.extend(["vertical angles diagram", "equal angles diagram"])
    elif "угл" in topic_l:
        short.extend(["equal angles diagram", "intersecting lines angles diagram"])

    if "similar" in terms:
        short.extend(["similar triangles diagram", "AA similar triangles"])
    if "vertical" in terms:
        short.append("vertical angles diagram")
    if "fraction" in terms or "fractions" in terms:
        short.extend(["fraction pie chart", "fraction circle diagram"])

    suffix = "diagram" if visual_type in ("diagram", "drawing", "formula") else "illustration"
    for q in ai_queries:
        words = [w for w in q.lower().split() if w not in QUERY_STOP_WORDS and len(w) > 2]
        if 2 <= len(words) <= 5:
            candidate = " ".join(words[:4]) + f" {suffix}"
            short.append(candidate)

    seen: set[str] = set()
    result: list[str] = []
    for s in short:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result[:8]


def _required_title_terms(topic: str, query_words: set[str], subject: str) -> set[str]:
    """Strict term matching only for geometry topics."""
    if subject not in GEOMETRY_SUBJECTS:
        return set()

    topic_l = topic.lower()
    terms: set[str] = set()

    if "треугольник" in topic_l or any(w in query_words for w in ("triangle", "triangles", "similar")):
        terms.update({"triangle", "triangles", "similar"})
    if "угл" in topic_l or any(w in query_words for w in ("angle", "angles", "vertical")):
        terms.update({"angle", "angles"})

    return terms


def _build_fallback_queries(topic: str, grade: int, subject: str) -> list[str]:
    return [f"{topic} diagram", f"simple {topic} illustration"]


async def _fetch_wikimedia(
    search_expr: str,
    client: httpx.AsyncClient,
    query_words: set[str],
) -> list[tuple[str, str, int, str]]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": search_expr,
        "gsrnamespace": "6",
        "gsrlimit": "20",
        "prop": "imageinfo",
        "iiprop": "url|mime|size|thumburl",
        "iiurlwidth": str(THUMB_WIDTH),
    }

    try:
        response = await client.get(WIKIMEDIA_API, params=params)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.warning(f"Wikimedia search failed for '{search_expr}': {e}")
        return []

    results: list[tuple[str, str, int, str]] = []
    for page in data.get("query", {}).get("pages", {}).values():
        title = page.get("title", "")
        imageinfo = page.get("imageinfo", [])
        if not imageinfo:
            continue

        info = imageinfo[0]
        mime = info.get("mime", "")
        width = info.get("width", 0)

        if not mime.startswith("image/") or width < MIN_WIDTH:
            continue

        score = _score_image(title, mime, query_words)
        if score < 0:
            continue

        url = info.get("thumburl") or info.get("url")
        if url:
            results.append((url, title, score, mime))

    return results


async def _search_wikimedia(
    query: str,
    client: httpx.AsyncClient,
    query_words: set[str],
) -> list[tuple[str, str, int, str]]:
    all_results: list[tuple[str, str, int, str]] = []
    seen: set[str] = set()

    for ftype in ("filetype:drawing", "filetype:bitmap|drawing"):
        expr = f"{ftype} {query}"
        for item in await _fetch_wikimedia(expr, client, query_words):
            if item[0] not in seen:
                seen.add(item[0])
                all_results.append(item)
        good = [r for r in all_results if r[2] >= MIN_ABSOLUTE_SCORE_GENERAL]
        if len(good) >= 2:
            break

    return all_results


def _select_best_images(
    candidates: list[tuple[str, str, int, str]],
    required_terms: set[str],
    subject: str,
) -> list[tuple[str, str, int]]:
    min_score = MIN_ABSOLUTE_SCORE if subject in GEOMETRY_SUBJECTS else MIN_ABSOLUTE_SCORE_GENERAL
    candidates.sort(key=lambda x: x[2], reverse=True)

    qualified = [(u, t, s) for u, t, s, m in candidates if s >= min_score]

    if required_terms:
        matched = [
            (u, t, s) for u, t, s in qualified
            if any(term in t.lower() for term in required_terms)
        ]
        if matched:
            qualified = matched
        else:
            qualified = [
                (u, t, s) for u, t, s, m in candidates
                if s >= 30 and any(term in t.lower() for term in required_terms)
            ]

    if not qualified:
        return []

    top_score = qualified[0][2]
    score_floor = max(min_score, int(top_score * 0.75))
    qualified = [(u, t, s) for u, t, s in qualified if s >= score_floor]

    return qualified[:MAX_IMAGES]


async def search_wikimedia_candidates(
    topic: str,
    subject: str,
    queries_en: list[str],
    visual_type: str = "illustration",
) -> list[ImageCandidate]:
    """Search Wikimedia Commons and return scored candidates."""
    search_queries = _build_short_queries(queries_en, topic, visual_type)
    if not search_queries:
        search_queries = queries_en[:5]

    logger.info(f"Wikimedia search queries: {search_queries}")

    query_words: set[str] = set()
    for q in search_queries + queries_en:
        for w in q.lower().split():
            if len(w) > 3:
                query_words.add(w)

    all_candidates: list[tuple[str, str, int, str]] = []
    seen_urls: set[str] = set()

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
        for query in search_queries:
            results = await _search_wikimedia(query, client, query_words)
            for url, title, score, mime in results:
                if url not in seen_urls:
                    seen_urls.add(url)
                    all_candidates.append((url, title, score, mime))

    required_terms = _required_title_terms(topic, query_words, subject)
    selected = _select_best_images(all_candidates, required_terms, subject)

    return [
        ImageCandidate(
            image_url=url,
            title=title,
            page_url=url,
            source="wikimedia",
            heuristic_score=score,
        )
        for url, title, score in selected
    ]


async def search_lesson_images(
    topic: str,
    grade: int,
    subject: str,
    content: Optional[LessonContent] = None,
    queries: Optional[list[str]] = None,
) -> list[str]:
    """Search Wikimedia Commons using AI-generated contextual queries."""
    visual_type = "illustration"
    if queries:
        ai_queries = queries[:5]
    elif content:
        pack = await generate_visual_queries(topic, grade, subject, content)
        ai_queries = pack.queries_en
        visual_type = pack.visual_type
    else:
        ai_queries = _build_fallback_queries(topic, grade, subject)

    candidates = await search_wikimedia_candidates(topic, subject, ai_queries, visual_type)
    found_urls = [c.image_url for c in candidates]

    for c in candidates:
        logger.info(f"  Selected image (score={c.heuristic_score}): {c.title}")

    logger.info(f"Found {len(found_urls)} images for topic '{topic}' ({subject})")
    return found_urls
