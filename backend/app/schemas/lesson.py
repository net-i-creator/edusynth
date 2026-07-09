from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from typing import Literal


class GenerateLessonRequest(BaseModel):
    topic: str
    grade: int
    subject: str
    education_level: Literal["school", "university", "extra"] = "school"


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: str | None = None


class LessonContent(BaseModel):
    title: str
    introduction: str
    main_content: str  # HTML with LaTeX
    examples: list[str]
    key_points: list[str]
    quiz: list[QuizQuestion]


class LessonResponse(BaseModel):
    id: UUID
    topic: str
    grade: int
    grade_label: str | None = None
    education_level: str = "school"
    subject: str
    content: LessonContent
    image_urls: list[str] | None
    created_at: datetime
    views_count: int

    model_config = {"from_attributes": True}


class LessonListItem(BaseModel):
    id: UUID
    topic: str
    grade: int
    grade_label: str | None = None
    education_level: str = "school"
    subject: str
    created_at: datetime
    views_count: int
    status: str | None = None
    score: int | None = None

    model_config = {"from_attributes": True}


class QuizSubmission(BaseModel):
    lesson_id: UUID
    answers: list[int]  # list of selected option indices


class QuizResult(BaseModel):
    total: int
    correct: int
    score_percent: int
    results: list[dict]  # [{question, selected, correct, is_correct}]
