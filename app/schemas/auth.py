from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    exp: int


class RefreshToken(BaseModel):
    refresh_token: str


class SessionInfo(BaseModel):
    user_id: int
    issued_at: datetime
    expires_at: datetime
    client: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    password: str


__all__ = [
    "Token",
    "TokenPayload",
    "RefreshToken",
    "SessionInfo",
    "PasswordResetRequest",
    "PasswordResetConfirm",
]
