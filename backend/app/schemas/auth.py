from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Literal


class UserRegister(BaseModel):
    email: str
    password: str
    full_name: str | None = None
    role: Literal["student", "parent", "teacher"] = "student"


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
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
