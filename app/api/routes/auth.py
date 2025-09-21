from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models import User
from app.schemas.auth import (
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshToken,
    Token,
)
from app.schemas.user import UserCreate, UserRead
from app.services import auth as auth_service
from app.services import email as email_service

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, session: Session = Depends(get_db)) -> UserRead:
    try:
        user = auth_service.register_user(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db),
) -> Token:
    user = auth_service.authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")

    return auth_service.issue_tokens(session, user, client=form_data.client_id)


@router.post("/refresh", response_model=Token)
def refresh_token(payload: RefreshToken, session: Session = Depends(get_db)) -> Token:
    try:
        return auth_service.rotate_refresh_token(session, payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def logout(payload: RefreshToken, session: Session = Depends(get_db)) -> None:
    auth_service.revoke_refresh_token(session, payload.refresh_token)


@router.post("/password/reset-request")
def password_reset_request(payload: PasswordResetRequest, session: Session = Depends(get_db)) -> dict[str, str]:
    result = auth_service.request_password_reset(session, payload.email)
    response: dict[str, str] = {
        "detail": "If an account exists for this email, a reset link has been prepared.",
    }
    if result is None:
        return response

    token, expires_at = result
    reset_link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={token}"
    email_package = email_service.prepare_password_reset_email(
        project_name=settings.project_name,
        user_email=payload.email,
        reset_link=reset_link,
        expires_at=expires_at.isoformat(),
    )
    email_service.log_email(email_package)

    if settings.debug:
        response["token"] = token
        response["reset_link"] = reset_link
        response["expires_at"] = expires_at.isoformat()

    return response


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def password_reset(payload: PasswordResetConfirm, session: Session = Depends(get_db)) -> None:
    try:
        auth_service.reset_password(session, payload.token, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)



