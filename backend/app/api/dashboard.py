from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.user import User
from app.models.lesson import Lesson
from app.models.progress import UserLessonProgress
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_dashboard_stats(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Total lessons viewed
    lessons_count = await db.execute(
        select(func.count(UserLessonProgress.id))
        .where(UserLessonProgress.user_id == user.id)
    )
    total_lessons = lessons_count.scalar() or 0

    # Completed lessons
    completed_count = await db.execute(
        select(func.count(UserLessonProgress.id))
        .where(UserLessonProgress.user_id == user.id)
        .where(UserLessonProgress.status == "completed")
    )
    completed = completed_count.scalar() or 0

    # Average score
    avg_score = await db.execute(
        select(func.avg(UserLessonProgress.score))
        .where(UserLessonProgress.user_id == user.id)
        .where(UserLessonProgress.status == "completed")
    )
    average_score = int(avg_score.scalar() or 0)

    # Subjects breakdown
    subjects = await db.execute(
        select(Lesson.subject, func.count(UserLessonProgress.id))
        .join(UserLessonProgress, UserLessonProgress.lesson_id == Lesson.id)
        .where(UserLessonProgress.user_id == user.id)
        .group_by(Lesson.subject)
    )
    subject_stats = {row[0]: row[1] for row in subjects.all()}

    return {
        "total_lessons": total_lessons,
        "completed": completed,
        "average_score": average_score,
        "subject_breakdown": subject_stats,
        "subscription": {
            "status": user.subscription_status,
            "expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
        },
    }
