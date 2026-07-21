from pydantic import BaseModel, field_validator
from uuid import UUID
from datetime import datetime
from typing import Literal
import re


PHONE_RE = re.compile(r"^(\+7|8)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$")


def normalize_phone(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) != 11 or not digits.startswith("7"):
        raise ValueError("Некорректный номер телефона")
    return f"+{digits}"


class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str | None = None
    phone: str | None = None
    role: Literal["student", "parent", "teacher"] = "student"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return normalize_phone(v)


class UserLogin(BaseModel):
    email: str
    password: str


class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    parent_name: str | None = None
    parent_phone: str | None = None

    @field_validator("phone", "parent_phone")
    @classmethod
    def validate_phones(cls, v: str | None) -> str | None:
        return normalize_phone(v)


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    phone: str | None = None
    parent_name: str | None = None
    parent_phone: str | None = None
    role: str
    subscription_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class SupportRequest(BaseModel):
    email: str
    message: str
