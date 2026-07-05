"""Vision-based verification of illustration candidates before adding to lessons."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re

import httpx

from app.config import get_settings
from app.schemas.lesson import LessonContent
from app.services.illustration_scoring import ImageCandidate

settings = get_settings()
logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
USER_AGENT = "Umbaza/1.0 (educational lesson generator; contact@umbaza.ru)"
MAX_IMAGE_BYTES = 2_500_000  # ~3.3MB base64, under Groq 4MB limit

VISION_USER_PROMPT = """Ты проверяешь картинку для школьного урока.

Тема урока: «{topic}»
Класс: {grade}, предмет: {subject}
Название картинки в поиске: «{title}»

Краткое содержание урока:
{summary}

Посмотри на изображение и оцени:
- approved (true/false): подходит ли как наглядная иллюстрация ИМЕННО к этой теме
- has_text (true/false): есть ли на картинке много текста (абзацы, слайд, конспект, таблица с текстом)
- is_simple (true/false): это простой рисунок/схема/чертёж/диаграмма (как в тетради)
- relevance (1-10): точность соответствия теме урока

ОБЯЗАТЕЛЬНО отклонить (approved=false):
- Слайд презентации, страница с текстом, конспект, фото учебника с текстом
- Много текста на изображении — даже если тема верная
- Карта, если урок НЕ про карты/географию/территории (история событий ≠ карта)
- Фото документа, скриншот сайта, мем, реклама, водяной знак
- Сложная перегруженная картинка, непонятная без текста
- Смежная подтема, не та что в уроке

Одобрить если: наглядная иллюстрация, минимум текста (подписи/формулы допустимы), relevance >= 7.

Ответ — ТОЛЬКО JSON:
{{"approved": true, "has_text": false, "is_simple": true, "relevance": 9, "reason": "кратко"}}"""


def _parse_vision_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    json_match = re.search(r"\{[\s\S]*\}", text)
    if not json_match:
        return None
    try:
        return json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return None


async def _download_image_base64(url: str) -> str | None:
    """Download image and return base64 data URL, or None on failure."""
    if url.startswith("data:"):
        return url

    try:
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(timeout=12.0, headers=headers, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
            if len(content) > MAX_IMAGE_BYTES:
                logger.info(f"Image too large for vision ({len(content)} bytes), skipping")
                return None

            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
            if not content_type.startswith("image/"):
                content_type = "image/jpeg"

            b64 = base64.b64encode(content).decode("ascii")
            return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning(f"Failed to download image for vision: {url[:80]} — {e}")
        return None


async def _call_groq_vision(data_url: str, prompt_text: str) -> dict | None:
    """Call Groq vision API with retries on rate limit."""
    body = {
        "model": settings.groq_vision_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": 200,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(GROQ_API_URL, json=body, headers=headers)
                if response.status_code == 429:
                    wait = 3 + attempt * 4
                    logger.warning(f"Groq vision rate limit, retry in {wait}s")
                    await asyncio.sleep(wait)
                    continue
                response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
            return _parse_vision_json(text)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < 2:
                await asyncio.sleep(3 + attempt * 4)
                continue
            raise
        except Exception:
            if attempt < 2:
                await asyncio.sleep(2)
                continue
            raise
    return None


async def _verify_one_groq_vision(
    candidate: ImageCandidate,
    topic: str,
    grade: int,
    subject: str,
    summary: str,
) -> tuple[ImageCandidate, bool | None]:
    """
    Verify a single candidate with Groq vision model.
    Returns (candidate, True/False) for approved/rejected, or None if verification failed.
    """
    if not settings.groq_api_key:
        return candidate, None

    data_url = await _download_image_base64(candidate.image_url)
    if not data_url:
        return candidate, None

    prompt_text = VISION_USER_PROMPT.format(
        topic=topic,
        grade=grade,
        subject=subject,
        title=candidate.title[:120],
        summary=summary[:600],
    )

    try:
        data = await _call_groq_vision(data_url, prompt_text)
        if not data:
            return candidate, None

        approved = (
            data.get("approved") is True
            and data.get("has_text") is not True
            and data.get("is_simple") is not False
            and int(data.get("relevance", 0)) >= 7
        )
        reason = data.get("reason", "")
        if approved:
            logger.info(f"  Vision APPROVED: {candidate.title[:50]} — {reason[:60]}")
        else:
            logger.info(
                f"  Vision REJECTED: {candidate.title[:50]} — "
                f"approved={data.get('approved')} has_text={data.get('has_text')} "
                f"rel={data.get('relevance')} — {reason[:60]}"
            )
        return candidate, approved
    except Exception as e:
        logger.warning(f"Vision verify failed for '{candidate.title[:40]}': {e}")
        return candidate, None


async def verify_images_with_vision(
    candidates: list[ImageCandidate],
    topic: str,
    grade: int,
    subject: str,
    content: LessonContent,
    max_approve: int,
) -> tuple[list[ImageCandidate], int]:
    """
    Verify each candidate image with AI vision before adding to the lesson.
    Returns (approved list, error_count).
    """
    if not candidates:
        return [], 0

    from app.services.yandex_ai import _lesson_text_summary

    summary = _lesson_text_summary(content)

    if not settings.image_vision_verify or not settings.groq_api_key:
        logger.info("Vision verify disabled or Groq key missing — skipping vision stage")
        return [], 0

    sem = asyncio.Semaphore(2)
    approved: list[ImageCandidate] = []
    errors = 0

    async def check(c: ImageCandidate) -> tuple[ImageCandidate, bool | None]:
        async with sem:
            return await _verify_one_groq_vision(c, topic, grade, subject, summary)

    # Check up to 8 candidates in small batches to avoid rate limits
    to_check = candidates[:8]
    for batch_start in range(0, len(to_check), 2):
        if len(approved) >= max_approve:
            break
        batch = to_check[batch_start : batch_start + 2]
        results = await asyncio.gather(*[check(c) for c in batch])
        for cand, result in results:
            if result is None:
                errors += 1
            elif result and len(approved) < max_approve:
                approved.append(cand)
        if batch_start + 2 < len(to_check):
            await asyncio.sleep(1)

    logger.info(
        f"Vision approved {len(approved)}/{len(to_check)} candidates for '{topic}' "
        f"({errors} errors)"
    )
    return approved, errors
