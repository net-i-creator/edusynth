import json
import re
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings
from app.schemas.lesson import LessonContent, QuizQuestion
from app.services.education_levels import build_lesson_user_prompt, get_system_prompt

settings = get_settings()
logger = logging.getLogger(__name__)

# Yandex endpoints
YANDEX_GPT_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
YANDEX_ART_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGeneration"

# Groq endpoint (OpenAI-compatible)
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """Ты — эксперт по созданию учебных материалов для школьников в России.
Твоя задача — создать качественный, понятный и структурированный урок.

Всегда отвечай ТОЛЬКО валидным JSON без markdown-обёрток. Формат:
{
  "title": "Название урока",
  "introduction": "Введение в тему (2-3 предложения)",
  "main_content": "Основной текст урока с HTML-разметкой и LaTeX-формулами (используй $...$ для инлайн и $$...$$ для блочных формул)",
  "examples": ["Пример 1 с решением", "Пример 2 с решением"],
  "key_points": ["Ключевой пункт 1", "Ключевой пункт 2", "Ключевой пункт 3"],
  "quiz": [
    {
      "question": "Вопрос?",
      "options": ["Вариант A", "Вариант B", "Вариант C", "Вариант D"],
      "correct_index": 0,
      "explanation": "Почему именно этот ответ правильный"
    }
  ]
}

Важно:
- Объясняй простым языком, подходящим для указанного класса
- Используй LaTeX для математических формул (используй $...$ для инлайн формул и $$...$$ для блочных)
- Создавай 4-5 вопросов для самопроверки
- Приводи конкретные примеры с решениями
- main_content должен содержать HTML: используй <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>
- НЕ используй markdown-разметку в main_content, только HTML"""


def fix_json_escapes(s: str) -> str:
    """Fix invalid JSON escape sequences from LaTeX (e.g. \\frac, \\sqrt)."""
    valid_escapes = {'"', '\\', '/', 'b', 'f', 'n', 'r', 't', 'u'}
    result = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            next_char = s[i + 1]
            if next_char in valid_escapes:
                result.append(s[i])
            else:
                result.append('\\\\')
            result.append(next_char)
            i += 2
        else:
            result.append(s[i])
            i += 1
    return ''.join(result)


def parse_ai_json(text: str, topic: str) -> LessonContent:
    """Parse AI response text into LessonContent."""
    text = text.strip()

    # Remove markdown code block wrappers
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Try to extract JSON from the text if it's embedded
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        text = json_match.group(0)

    # Fix invalid JSON escape sequences from LaTeX
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        fixed_text = fix_json_escapes(text)
        data = json.loads(fixed_text)

    quiz = [QuizQuestion(**q) for q in data.get("quiz", [])]

    return LessonContent(
        title=data.get("title", topic),
        introduction=data.get("introduction", ""),
        main_content=data.get("main_content", ""),
        examples=data.get("examples", []),
        key_points=data.get("key_points", []),
        quiz=quiz,
    )


async def generate_lesson_text_groq(
    topic: str,
    grade: int,
    subject: str,
    education_level: str = "school",
    grade_label: str | None = None,
) -> LessonContent:
    """Generate lesson using Groq API (OpenAI-compatible)."""
    if not settings.groq_api_key:
        raise ValueError("Groq API key не настроен. Добавьте GROQ_API_KEY в файл .env")

    label = grade_label or f"{grade} класс"
    user_prompt = build_lesson_user_prompt(topic, subject, education_level, grade, label)
    system_prompt = get_system_prompt(education_level)

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(GROQ_API_URL, json=body, headers=headers)
        response.raise_for_status()

    result = response.json()
    text = result["choices"][0]["message"]["content"]

    return parse_ai_json(text, topic)


async def generate_lesson_text_yandex(
    topic: str,
    grade: int,
    subject: str,
    education_level: str = "school",
    grade_label: str | None = None,
) -> LessonContent:
    """Generate lesson using YandexGPT API."""
    if not settings.yandex_api_key or not settings.yandex_folder_id:
        raise ValueError(
            "API-ключ Yandex Cloud не настроен. "
            "Добавьте YANDEX_API_KEY и YANDEX_FOLDER_ID в файл .env"
        )

    label = grade_label or f"{grade} класс"
    user_prompt = build_lesson_user_prompt(topic, subject, education_level, grade, label)
    system_prompt = get_system_prompt(education_level)

    headers = {
        "Authorization": f"Api-Key {settings.yandex_api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "modelUri": f"gpt://{settings.yandex_folder_id}/{settings.yandex_gpt_model}",
        "completionOptions": {
            "stream": False,
            "temperature": settings.yandex_gpt_temperature,
            "maxTokens": str(settings.yandex_gpt_max_tokens),
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(YANDEX_GPT_API_URL, json=body, headers=headers)
        response.raise_for_status()

    result = response.json()
    text = result["result"]["alternatives"][0]["message"]["text"]

    return parse_ai_json(text, topic)


async def generate_lesson_text(
    topic: str,
    grade: int,
    subject: str,
    education_level: str = "school",
    grade_label: str | None = None,
) -> LessonContent:
    """Route to the configured AI provider."""
    provider = settings.ai_provider.lower()
    label = grade_label or f"{grade}"
    if provider == "groq":
        logger.info(f"Generating lesson via Groq: {topic} ({education_level}, {label}, {subject})")
        return await generate_lesson_text_groq(topic, grade, subject, education_level, grade_label)
    else:
        logger.info(f"Generating lesson via YandexGPT: {topic} ({education_level}, {label}, {subject})")
        return await generate_lesson_text_yandex(topic, grade, subject, education_level, grade_label)


IMAGE_QUERY_SYSTEM_PROMPT = """Ты составляешь поисковые запросы для поиска НАГЛЯДНЫХ ИЛЛЮСТРАЦИЙ к школьному уроку.

Цель: найти простые рисунки как в тетрадном конспекте — чертежи, диаграммы, формулы, наглядные примеры.
НЕ ищи слайды презентаций, конспекты, текстовые страницы.

На основе содержания урока составь:
- 3 запроса на РУССКОМ (queries_ru) — для русскоязычного поиска
- 3 запроса на АНГЛИЙСКОМ (queries_en) — для Wikimedia/Openverse
- visual_type — тип визуала: diagram | formula | illustration | chart | drawing

Правила по предметам:
- Математика/дроби: «наглядно», «круг», «иллюстрация», «числовая прямая» — НЕ «умножение дробей» если тема «обыкновенные дроби»
- Геометрия: «чертёж», «рисунок», «diagram»
- Физика: «формула», «схема»
- Химия: «структура», «элемент», «молекула»
- История: «иллюстрация», «схема», «хронология», «рисунок» — НЕ «карта» если урок не про карты/географию
- Русский язык: «схема предложения», «разбор» — только если уместно

Критически важно:
- Ищи ТОЧНО по теме урока, не по смежным подтемам
- НЕ добавляй «схема» автоматически — только если уместно
- НЕ используй: конспект, презентация, ppt, реферат, тест, слайд

Примеры для «Обыкновенные дроби», 5 класс:
queries_ru: ["обыкновенные дроби наглядно круг иллюстрация 5 класс", "дробь часть целого рисунок", "обыкновенные дроби числовая прямая"]
queries_en: ["ordinary fractions pie chart illustration", "fraction circle diagram", "fraction number line"]
visual_type: "illustration"

Ответ — ТОЛЬКО JSON:
{"queries_ru": ["...", "...", "..."], "queries_en": ["...", "...", "..."], "visual_type": "illustration"}"""


IMAGE_VERIFY_SYSTEM_PROMPT = """Ты проверяешь, подходят ли найденные картинки для школьного урока.

Тебе дана тема урока, его содержание и список найденных картинок (название + источник).

Для каждой картинки оцени:
- relevance (1-10): насколько точно картинка соответствует ИМЕННО этой теме урока
- is_illustration (true/false): это простой наглядный рисунок/чертёж/диаграмма, а НЕ слайд с текстом
- likely_has_text (true/false): по названию похоже, что на картинке много текста (слайд, конспект, страница)
- reject (true/false): отклонить если не подходит

ОБЯЗАТЕЛЬНО отклонять (reject=true):
- Другая подтема (напр. «умножение дробей» когда урок про «обыкновенные дроби»)
- Презентация, ppt, слайд, конспект, тест, задание, документ в названии
- likely_has_text=true
- Историческая/политическая КАРТА — если урок НЕ про карты, географию, территории
- «Главные типы...» / «Все виды...» — слишком общая таблица
- relevance < 7

Выбери лучших до 10 кандидатов для дальнейшей проверки. Только простые иллюстрации без текста.

Ответ — ТОЛЬКО JSON:
{"selected": [{"index": 0, "relevance": 9, "is_illustration": true, "likely_has_text": false, "reject": false, "reason": "кратко"}]}"""


@dataclass
class VisualQueryPack:
    queries_ru: list[str]
    queries_en: list[str]
    visual_type: str = "illustration"


def _lesson_text_summary(content: LessonContent, max_chars: int = 1800) -> str:
    """Build a text summary of lesson content for image query generation."""
    main_text = re.sub(r"<[^>]+>", " ", content.main_content)
    main_text = re.sub(r"\s+", " ", main_text).strip()
    parts = [
        f"Название: {content.title}",
        f"Введение: {content.introduction}",
        f"Основное: {main_text[:900]}",
        "Ключевые пункты: " + "; ".join(content.key_points[:5]),
    ]
    return "\n".join(parts)[:max_chars]


def _parse_llm_json(text: str) -> dict:
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
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(fix_json_escapes(text))


def _parse_visual_queries_json(text: str) -> VisualQueryPack | None:
    data = _parse_llm_json(text)
    queries_ru = [q.strip() for q in data.get("queries_ru", []) if isinstance(q, str) and q.strip()][:3]
    queries_en = [q.strip() for q in data.get("queries_en", []) if isinstance(q, str) and q.strip()][:3]
    visual_type = data.get("visual_type", "illustration")
    if not isinstance(visual_type, str):
        visual_type = "illustration"

    # Backward compat: old format {"queries": [...]}
    if not queries_ru and not queries_en:
        legacy = [q.strip() for q in data.get("queries", []) if isinstance(q, str) and q.strip()][:3]
        if legacy:
            queries_ru = legacy

    if not queries_ru and not queries_en:
        return None

    return VisualQueryPack(
        queries_ru=queries_ru or queries_en,
        queries_en=queries_en or queries_ru,
        visual_type=visual_type,
    )


def _fallback_visual_queries(topic: str, grade: int, subject: str) -> VisualQueryPack:
    topic_l = topic.lower()
    if "дроб" in topic_l:
        return VisualQueryPack(
            queries_ru=[
                f"{topic} наглядно круг иллюстрация {grade} класс",
                f"{topic} рисунок часть целого",
                f"{topic} числовая прямая наглядно",
            ],
            queries_en=[
                "ordinary fractions pie chart illustration",
                "fraction circle diagram",
                "fraction number line diagram",
            ],
            visual_type="illustration",
        )
    if subject == "История" or "истори" in topic_l:
        return VisualQueryPack(
            queries_ru=[
                f"{topic} иллюстрация {grade} класс история",
                f"{topic} схема хронология рисунок",
                f"{topic} наглядно иллюстрация",
            ],
            queries_en=[
                f"{topic} history illustration",
                f"{topic} timeline diagram",
                f"{topic} educational drawing",
            ],
            visual_type="illustration",
        )
    return VisualQueryPack(
        queries_ru=[
            f"{topic} наглядно иллюстрация {grade} класс",
            f"{topic} рисунок {subject}",
            f"{topic} чертёж {grade} класс",
        ],
        queries_en=[
            f"{topic} illustration diagram",
            f"{topic} educational drawing",
            f"{topic} school diagram",
        ],
        visual_type="illustration",
    )


async def generate_visual_queries(
    topic: str,
    grade: int,
    subject: str,
    content: LessonContent,
) -> VisualQueryPack:
    """Use LLM to generate RU/EN visual search queries from lesson content."""
    summary = _lesson_text_summary(content)
    user_prompt = (
        f"Тема урока: «{topic}»\n"
        f"Класс: {grade}\n"
        f"Предмет: {subject}\n\n"
        f"Содержание урока:\n{summary}\n\n"
        f"Составь запросы для поиска простых наглядных иллюстраций (не слайдов, не конспектов)."
    )

    provider = settings.ai_provider.lower()
    try:
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
                    {"role": "system", "content": IMAGE_QUERY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 500,
                "response_format": {"type": "json_object"},
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(GROQ_API_URL, json=body, headers=headers)
                response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
        else:
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
                    "temperature": 0.3,
                    "maxTokens": "600",
                },
                "messages": [
                    {"role": "system", "text": IMAGE_QUERY_SYSTEM_PROMPT},
                    {"role": "user", "text": user_prompt},
                ],
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(YANDEX_GPT_API_URL, json=body, headers=headers)
                response.raise_for_status()
            text = response.json()["result"]["alternatives"][0]["message"]["text"]

        pack = _parse_visual_queries_json(text)
        if pack:
            logger.info(
                f"Visual queries for '{topic}': RU={pack.queries_ru}, EN={pack.queries_en}, "
                f"type={pack.visual_type}"
            )
            return pack
    except Exception as e:
        logger.warning(f"AI visual query generation failed: {e}")

    return _fallback_visual_queries(topic, grade, subject)


async def generate_image_search_queries(
    topic: str,
    grade: int,
    subject: str,
    content: LessonContent,
) -> list[str]:
    """Backward-compatible: returns English queries for Wikimedia standalone provider."""
    pack = await generate_visual_queries(topic, grade, subject, content)
    return pack.queries_en


async def _call_llm_json(system: str, user: str, max_tokens: int = 800) -> str:
    """Call configured LLM and return raw text response."""
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
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
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
            "temperature": 0.2,
            "maxTokens": str(max_tokens),
        },
        "messages": [
            {"role": "system", "text": system},
            {"role": "user", "text": user},
        ],
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(YANDEX_GPT_API_URL, json=body, headers=headers)
        response.raise_for_status()
    return response.json()["result"]["alternatives"][0]["message"]["text"]


async def verify_image_candidates(
    topic: str,
    grade: int,
    subject: str,
    content: LessonContent,
    candidates: list[dict],
    max_select: int = 3,
) -> list[int]:
    """Use LLM to verify and pick the most relevant illustration images."""
    if not candidates:
        return []

    summary = _lesson_text_summary(content)
    lines = []
    for i, c in enumerate(candidates[:20]):
        lines.append(f"{i}. «{c.get('title', '')}» — {c.get('page_url', '')}")

    user_prompt = (
        f"Тема урока: «{topic}»\n"
        f"Класс: {grade}, предмет: {subject}\n\n"
        f"Содержание:\n{summary}\n\n"
        f"Найденные картинки:\n" + "\n".join(lines)
    )

    try:
        text = await _call_llm_json(IMAGE_VERIFY_SYSTEM_PROMPT, user_prompt, max_tokens=600)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            text = json_match.group(0)
        data = json.loads(text)
    except Exception as e:
        logger.warning(f"Image verification failed: {e}")
        return []

    selected_indices: list[int] = []
    for item in data.get("selected", []):
        if not isinstance(item, dict):
            continue
        idx = item.get("index")
        if item.get("reject"):
            logger.info(f"  Rejected [{idx}]: {item.get('reason', '')}")
            continue
        if item.get("likely_has_text"):
            logger.info(f"  Rejected [{idx}] (likely text): {item.get('reason', '')}")
            continue
        is_ok = item.get("is_illustration") or item.get("is_scheme")
        if not is_ok:
            continue
        rel = item.get("relevance", 0)
        if rel < 7:
            continue
        if isinstance(idx, int) and 0 <= idx < len(candidates):
            selected_indices.append(idx)
            logger.info(f"  Verified [{idx}] rel={rel}: {item.get('reason', '')[:60]}")
        if len(selected_indices) >= max_select:
            break

    if not selected_indices:
        logger.info("Text verify returned empty selection")

    return selected_indices


async def generate_lesson_images(topic: str, grade: int, subject: str) -> list[str]:
    """Generate images using YandexART (only works with Yandex provider)."""
    if not settings.yandex_api_key or not settings.yandex_folder_id:
        logger.info("Skipping image generation: Yandex API not configured")
        return []

    prompts = [
        f"Учебная иллюстрация для урока: {topic}, {subject}, {grade} класс. Стиль: современный учебник, чистые линии, понятные схемы.",
        f"Диаграмма или схема по теме: {topic} для школьного урока {subject}.",
        f"Наглядный пример по теме {topic}, подходящий для учеников {grade} класса.",
    ]

    image_urls = []

    headers = {
        "Authorization": f"Api-Key {settings.yandex_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        for prompt in prompts:
            try:
                body = {
                    "modelUri": f"art://{settings.yandex_folder_id}/{settings.yandex_art_model}",
                    "messages": [
                        {"text": prompt, "weight": 1}
                    ],
                    "width": 1024,
                    "height": 768,
                }

                response = await client.post(YANDEX_ART_API_URL, json=body, headers=headers)
                response.raise_for_status()

                result = response.json()
                image_data = result.get("image", "")
                if image_data:
                    image_urls.append(f"data:image/png;base64,{image_data}")
                else:
                    logger.warning(f"No image data in response for prompt: {prompt[:50]}")

            except Exception as e:
                logger.error(f"Image generation failed for prompt: {e}")
                continue

    return image_urls
