import uuid
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.user import User
from app.models.lesson import Lesson
from app.models.progress import UserLessonProgress
from app.schemas.lesson import GenerateLessonRequest, LessonResponse, LessonContent, LessonListItem
from app.api.deps import get_current_user, optional_security
from app.services.auth import get_user_by_id
from app.services.cache import generate_topic_hash, get_cached_lesson, cache_lesson
from app.services.yandex_ai import generate_lesson_text
from app.services.illustrations import get_lesson_illustrations
from app.services.education_levels import validate_lesson_params
from app.services.guest_limit import check_guest_can_generate, record_guest_generation

import jwt
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lessons", tags=["lessons"])


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Returns user if token is valid, None otherwise."""
    if not credentials:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = uuid.UUID(payload["sub"])
        return await get_user_by_id(db, user_id)
    except Exception:
        return None


def _lesson_to_response(lesson: Lesson, content: LessonContent | None = None) -> LessonResponse:
    return LessonResponse(
        id=lesson.id,
        topic=lesson.topic,
        grade=lesson.grade,
        grade_label=lesson.grade_label,
        education_level=lesson.education_level or "school",
        subject=lesson.subject,
        content=content or LessonContent(**lesson.content_json),
        image_urls=lesson.image_urls,
        created_at=lesson.created_at,
        views_count=lesson.views_count,
    )


@router.post("/generate", response_model=LessonResponse)
async def generate_lesson(
    data: GenerateLessonRequest,
    user: Annotated[Optional[User], Depends(get_optional_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_guest_id: Annotated[str | None, Header()] = None,
):
    grade_label = validate_lesson_params(data.education_level, data.grade)
    topic_hash = generate_topic_hash(data.topic, data.grade, data.subject, data.education_level)

    cached = await get_cached_lesson(topic_hash)
    if cached:
        result = await db.execute(select(Lesson).where(Lesson.topic_hash == topic_hash))
        lesson = result.scalar_one_or_none()

        if not cached.get("image_urls") and lesson and lesson.content_json:
            try:
                content = LessonContent(**lesson.content_json)
                image_urls = await get_lesson_illustrations(
                    data.topic, data.grade, data.subject, content=content
                )
                if image_urls:
                    lesson.image_urls = image_urls
                    cached["image_urls"] = image_urls
                    await db.commit()
                    await cache_lesson(topic_hash, cached)
                    logger.info(f"Regenerated {len(image_urls)} illustrations for cached '{data.topic}'")
            except Exception as e:
                logger.warning(f"Illustration regen for cached lesson failed: {e}")

        if lesson:
            lesson.views_count += 1
            await db.commit()

        if lesson and user:
            progress = UserLessonProgress(user_id=user.id, lesson_id=lesson.id)
            db.add(progress)
            await db.commit()

        return LessonResponse(**cached)

    if not user:
        if not x_guest_id:
            raise HTTPException(status_code=400, detail="X-Guest-Id header required for anonymous users")
        await check_guest_can_generate(x_guest_id)

    try:
        content = await generate_lesson_text(
            data.topic,
            data.grade,
            data.subject,
            data.education_level,
            grade_label,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI generation failed: {str(e)}")

    image_urls = []
    try:
        image_urls = await get_lesson_illustrations(
            data.topic, data.grade, data.subject, content=content
        )
    except Exception as e:
        logger.warning(f"Illustration generation failed for '{data.topic}': {e}")

    lesson = Lesson(
        topic_hash=topic_hash,
        topic=data.topic,
        education_level=data.education_level,
        grade=data.grade,
        grade_label=grade_label,
        subject=data.subject,
        content_json=content.model_dump(),
        image_urls=image_urls if image_urls else None,
    )
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)

    if user:
        progress = UserLessonProgress(user_id=user.id, lesson_id=lesson.id)
        db.add(progress)
        await db.commit()
    elif x_guest_id:
        await record_guest_generation(x_guest_id)

    response_data = {
        "id": str(lesson.id),
        "topic": lesson.topic,
        "grade": lesson.grade,
        "grade_label": lesson.grade_label,
        "education_level": lesson.education_level,
        "subject": lesson.subject,
        "content": content.model_dump(),
        "image_urls": lesson.image_urls,
        "created_at": lesson.created_at.isoformat(),
        "views_count": lesson.views_count,
    }
    await cache_lesson(topic_hash, response_data)

    return _lesson_to_response(lesson, content)


@router.get("/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    lesson_id: uuid.UUID,
    user: Annotated[Optional[User], Depends(get_optional_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    lesson.views_count += 1
    await db.commit()

    return _lesson_to_response(lesson)


@router.get("/history/", response_model=list[LessonListItem])
async def get_lesson_history(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(Lesson, UserLessonProgress)
        .join(UserLessonProgress, UserLessonProgress.lesson_id == Lesson.id)
        .where(UserLessonProgress.user_id == user.id)
        .order_by(UserLessonProgress.started_at.desc())
        .limit(50)
    )
    rows = result.all()

    items = []
    for lesson, progress in rows:
        items.append(LessonListItem(
            id=lesson.id,
            topic=lesson.topic,
            grade=lesson.grade,
            grade_label=lesson.grade_label,
            education_level=lesson.education_level or "school",
            subject=lesson.subject,
            created_at=lesson.created_at,
            views_count=lesson.views_count,
            status=progress.status,
            score=progress.score,
        ))

    return items
