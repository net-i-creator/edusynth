import base64
import json
import logging
import re

import httpx

from app.config import get_settings
from app.schemas.lesson import LessonContent
from app.services.yandex_ai import (
    GROQ_API_URL,
    YANDEX_GPT_API_URL,
    _lesson_text_summary,
    fix_json_escapes,
)

settings = get_settings()
logger = logging.getLogger(__name__)

MAX_SVGS = 2
MAX_SVG_BYTES = 48_000

SVG_SYSTEM_PROMPT = """Ты создаёшь простые учебные SVG-иллюстрации для школьного урока в России.

На основе содержания урока создай ровно 2 SVG-схемы в стиле школьного учебника.

Требования к каждой SVG:
- viewBox="0 0 400 280", width="400" height="280"
- Светлый фон: <rect width="400" height="280" fill="#f4f6f8"/>
- Чистые линии, простые фигуры: line, rect, circle, path, polygon, text
- Подписи ТОЛЬКО на русском языке
- Показывай конкретные примеры из темы урока (предложения, схемы, формулы, диаграммы)
- Уровень сложности — для указанного класса
- Без <script>, без внешних ссылок, без <image>, без анимаций
- Цвета: линии #2d3748, акцент #3b82f6, текст #1a202c

Для русского языка: схемы разбора предложений, стрелки к подлежащему/сказуемому, примеры предложений.
Для математики: геометрические фигуры, углы, подписи сторон.
Для других предметов: простые понятные схемы по теме.

Ответ — ТОЛЬКО валидный JSON без markdown:
{"svgs": ["<svg xmlns=\\"http://www.w3.org/2000/svg\\" ...>...</svg>", "<svg ...>...</svg>"]}"""


def _parse_svgs_json(text: str) -> list[str]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        text = json_match.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = json.loads(fix_json_escapes(text))

    svgs = data.get("svgs", [])
    return [s.strip() for s in svgs if isinstance(s, str) and s.strip()]


def _sanitize_svg(svg: str) -> str | None:
    """Remove unsafe content and ensure valid SVG wrapper."""
    svg = svg.strip()
    if not svg.lower().startswith("<svg"):
        match = re.search(r"<svg[\s\S]*</svg>", svg, re.IGNORECASE)
        if not match:
            return None
        svg = match.group(0)

    if len(svg.encode("utf-8")) > MAX_SVG_BYTES:
        return None

    lowered = svg.lower()
    for forbidden in ("<script", "javascript:", "onload=", "onclick=", "<foreignobject", "xlink:href=", "<image"):
        if forbidden in lowered:
            return None

    if 'xmlns=' not in svg[:200].lower():
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)

    return svg


def _svg_to_data_uri(svg: str) -> str:
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


async def _call_llm(system: str, user: str, max_tokens: int = 3500) -> str:
    provider = settings.ai_provider.lower()

    if provider == "groq":
        if not settings.groq_api_key:
            raise ValueError("Groq API key not configured")
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": settings.groq_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.4,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(GROQ_API_URL, json=body, headers=headers)
            response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    if not settings.yandex_api_key or not settings.yandex_folder_id:
        raise ValueError("Yandex API not configured")

    headers = {
        "Authorization": f"Api-Key {settings.yandex_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "modelUri": f"gpt://{settings.yandex_folder_id}/{settings.yandex_gpt_model}",
        "completionOptions": {
            "stream": False,
            "temperature": 0.4,
            "maxTokens": str(max_tokens),
        },
        "messages": [
            {"role": "system", "text": system},
            {"role": "user", "text": user},
        ],
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(YANDEX_GPT_API_URL, json=body, headers=headers)
        response.raise_for_status()
    return response.json()["result"]["alternatives"][0]["message"]["text"]


async def generate_lesson_svgs(
    topic: str,
    grade: int,
    subject: str,
    content: LessonContent,
) -> list[str]:
    """Generate contextual textbook-style SVG illustrations via LLM."""
    summary = _lesson_text_summary(content)
    user_prompt = (
        f"Тема: «{topic}»\n"
        f"Класс: {grade}\n"
        f"Предмет: {subject}\n\n"
        f"Содержание урока:\n{summary}\n\n"
        f"Создай 2 простые SVG-схемы именно по этой теме для учеников {grade} класса."
    )

    try:
        text = await _call_llm(SVG_SYSTEM_PROMPT, user_prompt)
        raw_svgs = _parse_svgs_json(text)
    except Exception as e:
        logger.warning(f"SVG illustration generation failed: {e}")
        return []

    urls: list[str] = []
    for raw in raw_svgs[:MAX_SVGS]:
        clean = _sanitize_svg(raw)
        if clean:
            urls.append(_svg_to_data_uri(clean))

    logger.info(f"Generated {len(urls)} SVG illustrations for '{topic}' ({subject})")
    return urls
