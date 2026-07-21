from typing import Annotated
import asyncio
import logging
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    TokenRefresh,
    UserProfileUpdate,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.services.auth import (
    register_user,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_id,
    get_user_by_email,
    set_user_password,
)
from app.services.cache import store_password_reset_token, consume_password_reset_token
from app.services.email import send_password_reset_email
from app.services.sheets import upsert_user_row, sync_all_users, sheets_configured
from app.api.deps import get_current_user
from app.models.user import User
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _require_auth_enabled() -> None:
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Регистрация и вход временно недоступны",
        )


def _schedule_sheets_upsert(user: User) -> None:
    if not sheets_configured():
        return
    from types import SimpleNamespace

    # Snapshot plain fields — ORM instance may expire after the request session closes
    snapshot = SimpleNamespace(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        parent_name=user.parent_name,
        parent_phone=user.parent_phone,
        subscription_status=user.subscription_status,
        role=user.role,
        created_at=user.created_at,
    )

    async def _run():
        try:
            await asyncio.to_thread(upsert_user_row, snapshot)
        except Exception:
            logger.exception("Background sheets upsert failed")

    try:
        asyncio.create_task(_run())
    except RuntimeError:
        upsert_user_row(snapshot)


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, db: Annotated[AsyncSession, Depends(get_db)]):
    _require_auth_enabled()
    try:
        user = await register_user(
            db, data.email, data.password, data.full_name, data.phone, data.role
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    _schedule_sheets_upsert(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: Annotated[AsyncSession, Depends(get_db)]):
    _require_auth_enabled()
    user = await authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Always returns success to avoid email enumeration."""
    _require_auth_enabled()
    email = data.email.strip().lower()
    user = await get_user_by_email(db, email)
    if not user:
        # Try original casing match for legacy rows
        result = await db.execute(select(User).where(User.email == data.email.strip()))
        user = result.scalar_one_or_none()

    if user:
        token = secrets.token_urlsafe(32)
        stored = await store_password_reset_token(
            token,
            user.id,
            ttl_seconds=settings.password_reset_expire_minutes * 60,
        )
        if stored:
            reset_url = (
                f"{settings.frontend_url.rstrip('/')}/auth.html"
                f"?mode=reset&token={quote(token)}"
            )
            send_password_reset_email(user.email, reset_url)
        else:
            logger.error("Could not store password reset token (Redis unavailable?)")

    return {
        "ok": True,
        "detail": "Если аккаунт с таким email существует, мы отправили ссылку для сброса пароля.",
    }


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    _require_auth_enabled()
    if len(data.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароль должен содержать минимум 6 символов",
        )

    user_id = await consume_password_reset_token(data.token.strip())
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ссылка недействительна или устарела. Запросите сброс пароля снова.",
        )

    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь не найден")

    await set_user_password(db, user, data.password)
    return {"ok": True, "detail": "Пароль обновлён. Теперь можно войти."}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: TokenRefresh):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        from uuid import UUID
        user_id = UUID(payload["sub"])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: Annotated[User, Depends(get_current_user)]):
    return user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if data.full_name is not None:
        user.full_name = data.full_name or None
    if data.phone is not None:
        user.phone = data.phone or None
    if data.parent_name is not None:
        user.parent_name = data.parent_name or None
    if data.parent_phone is not None:
        user.parent_phone = data.parent_phone or None

    await db.commit()
    await db.refresh(user)
    _schedule_sheets_upsert(user)
    return user


@router.post("/sync-sheets")
async def sync_sheets(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_admin_secret: Annotated[str | None, Header()] = None,
):
    """Full rebuild of the users Google Sheet. Protected by ADMIN_SYNC_SECRET."""
    if not settings.admin_sync_secret or x_admin_secret != settings.admin_sync_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if not sheets_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Sheets не настроен",
        )

    result = await db.execute(select(User).order_by(User.created_at.asc()))
    users = list(result.scalars().all())
    count = await asyncio.to_thread(sync_all_users, users)
    return {"ok": True, "synced": count}
