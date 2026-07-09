"""Education level validation and prompt helpers."""

from fastapi import HTTPException

EDUCATION_LEVELS = ("school", "university", "extra")

EXTRA_GRADE_LABELS = {1: "Базовый", 2: "Продвинутый", 3: "Экспертный"}

ROLE_LABELS = {
    "student": "Ученик",
    "parent": "Родитель",
    "teacher": "Преподаватель",
}


def validate_lesson_params(education_level: str, grade: int) -> str:
    """Validate grade for education level and return display label."""
    if education_level not in EDUCATION_LEVELS:
        raise HTTPException(status_code=400, detail="Invalid education level")

    if education_level == "school":
        if grade < 5 or grade > 11:
            raise HTTPException(status_code=400, detail="Grade must be between 5 and 11")
        return f"{grade} класс"

    if education_level == "university":
        if grade < 1 or grade > 6:
            raise HTTPException(status_code=400, detail="Course must be between 1 and 6")
        return f"{grade} курс"

    if grade not in EXTRA_GRADE_LABELS:
        raise HTTPException(status_code=400, detail="Level must be 1 (basic), 2 (advanced), or 3 (expert)")
    return EXTRA_GRADE_LABELS[grade]


def build_lesson_user_prompt(
    topic: str,
    subject: str,
    education_level: str,
    grade: int,
    grade_label: str,
) -> str:
    if education_level == "school":
        return (
            f"Создай урок по теме «{topic}» для {grade_label} по предмету «{subject}».\n"
            f"Уровень сложности должен соответствовать возрасту учеников {grade} класса.\n"
            f"Отвечай ТОЛЬКО валидным JSON."
        )

    if education_level == "university":
        return (
            f"Создай учебный материал по теме «{topic}» для студентов {grade_label} "
            f"по дисциплине «{subject}» (высшее образование, Россия).\n"
            f"Уровень: академический, но понятный. Включи определения, примеры, практику.\n"
            f"Отвечай ТОЛЬКО валидным JSON."
        )

    return (
        f"Создай обучающий материал по теме «{topic}» (дополнительное образование, уровень «{grade_label}») "
        f"по направлению «{subject}».\n"
        f"Стиль: практический курс, чёткая структура, примеры из жизни.\n"
        f"Отвечай ТОЛЬКО валидным JSON."
    )


def get_system_prompt(education_level: str) -> str:
    base_json = """
Всегда отвечай ТОЛЬКО валидным JSON без markdown-обёрток. Формат:
{
  "title": "Название урока",
  "introduction": "Введение в тему (2-3 предложения)",
  "main_content": "Основной текст с HTML-разметкой и LaTeX ($...$ инлайн, $$...$$ блочные)",
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

- Используй LaTeX для формул
- Создавай 4-5 вопросов для самопроверки
- main_content: HTML (<h2>, <h3>, <p>, <ul>, <li>, <strong>), без markdown"""

    if education_level == "school":
        return (
            "Ты — эксперт по созданию учебных материалов для школьников в России.\n"
            "Твоя задача — создать качественный, понятный и структурированный урок.\n"
            + base_json
            + "\n- Объясняй простым языком, подходящим для указанного класса"
        )

    if education_level == "university":
        return (
            "Ты — эксперт по созданию учебных материалов для студентов вузов в России.\n"
            "Твоя задача — создать структурированный учебный модуль по дисциплине.\n"
            + base_json
            + "\n- Уровень: высшее образование, академическая точность"
        )

    return (
        "Ты — эксперт по дополнительному и профессиональному образованию в России.\n"
        "Твоя задача — создать практический обучающий материал для курса.\n"
        + base_json
        + "\n- Фокус на практическом применении знаний"
    )


def education_level_label(level: str) -> str:
    return {"school": "Школа", "university": "ВУЗ", "extra": "Доп. образование"}.get(level, level)
