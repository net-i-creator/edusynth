from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.auth import UserRegister, UserLogin, UserResponse, TokenResponse, TokenRefresh, UserProfileUpdate
from app.services.auth import register_user, authenticate_user, create_access_token, create_refresh_token, decode_token, get_user_by_id
from app.api.deps import get_current_user
from app.models.user import User
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _require_auth_enabled() -> None:
    if not settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Регистрация и вход временно недоступны",
        )


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, db: Annotated[AsyncSession, Depends(get_db)]):
    _require_auth_enabled()
    try:
        user = await register_user(
            db, data.email, data.password, data.full_name, data.phone, data.role
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

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
    return user
