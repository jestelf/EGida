from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models import PasswordResetToken, RefreshToken, User
from app.schemas.auth import Token
from app.schemas.user import UserCreate

_ACCESS_TOKEN_EXPIRES_IN = settings.access_token_expire_minutes * 60
_PASSWORD_RESET_EXPIRES = timedelta(hours=24)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_user(session: Session, payload: UserCreate) -> User:
    existing_user = session.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise ValueError("User already exists")

    user = User(email=payload.email, hashed_password=get_password_hash(payload.password))
    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ValueError("Could not create user") from exc

    session.refresh(user)
    return user


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def issue_tokens(session: Session, user: User, client: str | None = None) -> Token:
    access_token = create_access_token(str(user.id))
    refresh_token, refresh_expires_at = create_refresh_token(str(user.id))

    refresh_entity = RefreshToken(
        user_id=user.id,
        token=_hash_token(refresh_token),
        expires_at=refresh_expires_at,
        client=client,
    )
    session.add(refresh_entity)
    session.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=_ACCESS_TOKEN_EXPIRES_IN,
    )


def rotate_refresh_token(session: Session, token_str: str, client: str | None = None) -> Token:
    try:
        payload = decode_token(token_str)
    except JWTError as exc:
        raise ValueError("Invalid refresh token") from exc

    if payload.get("type") != "refresh":
        raise ValueError("Invalid token type")

    refresh_record = _get_refresh_token(session, token_str)
    if refresh_record is None:
        raise ValueError("Invalid refresh token")

    if refresh_record.revoked:
        raise ValueError("Refresh token revoked")

    if refresh_record.expires_at <= datetime.utcnow():
        raise ValueError("Refresh token expired")

    user = session.get(User, refresh_record.user_id)
    if user is None:
        raise ValueError("User not found")

    refresh_record.revoked = True
    session.add(refresh_record)
    session.commit()

    return issue_tokens(session, user, client=client)


def revoke_refresh_token(session: Session, token_str: str) -> None:
    refresh_record = _get_refresh_token(session, token_str)
    if refresh_record is None:
        return

    refresh_record.revoked = True
    session.add(refresh_record)
    session.commit()


def request_password_reset(session: Session, email: str) -> tuple[str, datetime] | None:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        return None

    now = datetime.utcnow()
    for existing in session.scalars(
        select(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id)
        .where(PasswordResetToken.used.is_(False))
    ):
        existing.used = True
        existing.used_at = now
        session.add(existing)

    raw_token = secrets.token_urlsafe(48)
    reset_record = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=now + _PASSWORD_RESET_EXPIRES,
    )
    session.add(reset_record)
    session.commit()

    return raw_token, reset_record.expires_at


def reset_password(session: Session, token: str, new_password: str) -> None:
    hashed = _hash_token(token)
    reset_record = session.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hashed))
    if reset_record is None:
        raise ValueError("Invalid or expired token")

    now = datetime.utcnow()
    if reset_record.used or reset_record.expires_at <= now:
        raise ValueError("Invalid or expired token")

    user = session.get(User, reset_record.user_id)
    if user is None:
        raise ValueError("User not found")

    user.hashed_password = get_password_hash(new_password)
    reset_record.used = True
    reset_record.used_at = now

    for refresh in session.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id)):
        refresh.revoked = True
        session.add(refresh)

    session.add_all([user, reset_record])
    session.commit()


def _get_refresh_token(session: Session, token_str: str) -> RefreshToken | None:
    hashed = _hash_token(token_str)
    return session.scalar(select(RefreshToken).where(RefreshToken.token == hashed))
