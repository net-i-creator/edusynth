import uuid
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, Float, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    education_level: Mapped[str] = mapped_column(
        SAEnum("school", "university", "extra", name="education_level"),
        default="school",
        server_default="school",
    )
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    grade_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subject: Mapped[str] = mapped_column(String(100), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    image_urls: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    views_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    generation_cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    progress: Mapped[list["UserLessonProgress"]] = relationship(back_populates="lesson")

    def __repr__(self) -> str:
        return f"<Lesson {self.topic} ({self.grade} класс)>"
