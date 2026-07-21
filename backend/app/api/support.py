from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.email import send_support_notification

router = APIRouter(prefix="/api", tags=["support"])
settings = get_settings()


class SupportPayload(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    message: str = Field(min_length=3, max_length=5000)


@router.post("/support")
async def submit_support(data: SupportPayload):
    email = data.email.strip()
    message = data.message.strip()
    if "@" not in email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный email")
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Введите сообщение")

    sent = send_support_notification(email, message)
    if not sent:
        # Still accept the request — HandyHost PHP fallback may also handle this,
        # and we don't want to lose the user's message in the UI.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Не удалось отправить сообщение. Напишите на " + settings.support_email,
        )

    return {
        "ok": True,
        "detail": f"Сообщение отправлено на {settings.support_email}",
    }
