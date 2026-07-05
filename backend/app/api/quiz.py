from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.user import User
from app.models.lesson import Lesson
from app.models.progress import UserLessonProgress
from app.schemas.lesson import QuizSubmission, QuizResult
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/quiz", tags=["quiz"])


@router.post("/check", response_model=QuizResult)
async def check_quiz(
    data: QuizSubmission,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Get lesson
    result = await db.execute(select(Lesson).where(Lesson.id == data.lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    quiz = lesson.content_json.get("quiz", [])
    if not quiz:
        raise HTTPException(status_code=400, detail="No quiz found for this lesson")

    if len(data.answers) != len(quiz):
        raise HTTPException(status_code=400, detail=f"Expected {len(quiz)} answers, got {len(data.answers)}")

    # Check answers
    results = []
    correct_count = 0
    for i, (question, answer) in enumerate(zip(quiz, data.answers)):
        is_correct = answer == question["correct_index"]
        if is_correct:
            correct_count += 1
        results.append({
            "question": question["question"],
            "selected": answer,
            "correct": question["correct_index"],
            "is_correct": is_correct,
            "explanation": question.get("explanation", ""),
        })

    score_percent = int((correct_count / len(quiz)) * 100)

    # Update progress
    progress_result = await db.execute(
        select(UserLessonProgress)
        .where(UserLessonProgress.user_id == user.id)
        .where(UserLessonProgress.lesson_id == data.lesson_id)
        .order_by(UserLessonProgress.started_at.desc())
        .limit(1)
    )
    progress = progress_result.scalar_one_or_none()

    if progress:
        progress.status = "completed"
        progress.score = score_percent
        progress.quiz_answers = {"answers": data.answers, "results": results}
        progress.completed_at = datetime.now(timezone.utc)
        await db.commit()

    return QuizResult(
        total=len(quiz),
        correct=correct_count,
        score_percent=score_percent,
        results=results,
    )
