"""Unified scoring and candidate merging for lesson illustrations."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ImageCandidate:
    image_url: str
    title: str
    page_url: str
    source: str
    heuristic_score: int = 0

    def to_dict(self) -> dict:
        return {
            "image_url": self.image_url,
            "title": self.title,
            "page_url": self.page_url,
            "source": self.source,
            "heuristic_score": self.heuristic_score,
        }


BLOCKLIST = (
    "grammar tree", "syntax tree", "japanese", "chinese", "english grammar",
    "anatomy", "medical", "shutterstock", "getty", "wallpaper", "meme",
    "alamy", "istock", "depositphotos",
)

TEXT_PENALTY = (
    "конспект", "реферат", "доклад", "текст", "определение", "контрольная",
    "тест", "задание", "ответы", "разбор текста", "сочинение",
    "презентация", "ppt", "slide", "ppt-online", "ppt4web", "powerpoint",
    "presentation", "online presentation",
)

BROAD_PENALTY = (
    "главные типы", "все виды", "виды и типы", "классификация всех",
    "основные типы",
)

ILLUSTRATION_BOOST = (
    "иллюстрация", "рисунок", "наглядно", "нагляд", "чертёж", "чертеж",
    "diagram", "illustration", "drawing", "figure", "sketch", "chart",
    "formula", "схема", "структур",
)

HISTORY_SUBJECTS = frozenset({"История", "Обществознание", "География"})

MAP_PENALTY = (
    "historical map", "political map", "карта", "map of", "atlas",
    "картограф", "географическ",
)

TEXT_HEAVY_PENALTY = (
    "document", "manuscript", "newspaper", "article", "page scan",
    "газета", "документ", "страница",
)

EDU_DOMAINS = (
    "wikimedia", "commons.wikimedia", "openverse", "1sept.ru",
    "uchitel.pro", "znanio", "infourok", "pedportal", "yaklass",
    "foxford", "skysmart", "obrazovaka", "gramota",
)


def _topic_tokens(topic: str) -> set[str]:
    stop = {"урок", "класс", "тема", "изучение", "понятие"}
    return {
        w for w in re.findall(r"[а-яёa-z0-9]+", topic.lower())
        if len(w) > 3 and w not in stop
    }


def score_candidate(
    title: str,
    page_url: str,
    image_url: str,
    topic: str,
    subject: str = "",
    width: int = 0,
    height: int = 0,
) -> int:
    """Score an image candidate. Higher is better; negative means reject."""
    t = (title or "").lower()
    combined = f"{t} {page_url} {image_url}".lower()
    score = 0

    for kw in BLOCKLIST:
        if kw in combined:
            return -1000

    for kw in TEXT_PENALTY:
        if kw in t:
            score -= 30

    for kw in TEXT_HEAVY_PENALTY:
        if kw in t:
            score -= 35

    topic_l = topic.lower()
    map_ok = subject in ("География",) or any(w in topic_l for w in ("карт", "map", "территор", "географ"))
    if not map_ok:
        for kw in MAP_PENALTY:
            if kw in t:
                score -= 40

    for kw in BROAD_PENALTY:
        if kw in t:
            score -= 20

    for kw in ILLUSTRATION_BOOST:
        if kw in t:
            score += 18

    for domain in EDU_DOMAINS:
        if domain in combined:
            score += 25
            break

    topic_toks = _topic_tokens(topic)
    matched = sum(1 for w in topic_toks if w in combined)
    score += matched * 22

    subtopic_markers = ("определительн", "изъяснительн", "обстоятельственн", "сравнительн")
    if any(m in t for m in subtopic_markers):
        if not any(m in topic.lower() for m in subtopic_markers):
            score -= 35

    if width >= 700 and height >= 450:
        score += 12
    elif width >= 500 and height >= 350:
        score += 6

    return score


def merge_candidates(pools: list[list[ImageCandidate]]) -> list[ImageCandidate]:
    """Merge candidate pools, deduplicating by image URL (keep highest score)."""
    by_url: dict[str, ImageCandidate] = {}
    for pool in pools:
        for c in pool:
            existing = by_url.get(c.image_url)
            if existing is None or c.heuristic_score > existing.heuristic_score:
                by_url[c.image_url] = c

    merged = sorted(by_url.values(), key=lambda c: c.heuristic_score, reverse=True)
    return merged


def heuristic_shortlist(
    candidates: list[ImageCandidate],
    max_count: int = 8,
    min_score: int = 15,
) -> list[ImageCandidate]:
    """Fallback shortlist when LLM text verify fails or returns nothing."""
    valid = [c for c in candidates if c.heuristic_score >= min_score]
    return valid[:max_count]


def top_heuristic(candidates: list[ImageCandidate], max_count: int = 3) -> list[ImageCandidate]:
    """Return top candidates by score, excluding blocked ones."""
    valid = [c for c in candidates if c.heuristic_score >= 0]
    return valid[:max_count]
