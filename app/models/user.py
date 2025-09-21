from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:  # pragma: no cover - typing helpers only
    from app.models import (
        AuditLog,
        GroupMembership,
        Organization,
        OrganizationInvite,
        OrganizationMember,
        PasswordResetToken,
        RefreshToken,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    owned_organizations: Mapped[list["Organization"]] = relationship(
        "Organization", back_populates="owner"
    )
    memberships: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember", back_populates="user"
    )
    group_memberships: Mapped[list["GroupMembership"]] = relationship(
        "GroupMembership", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    sent_invites: Mapped[list["OrganizationInvite"]] = relationship(
        "OrganizationInvite", back_populates="invited_by", foreign_keys="OrganizationInvite.invited_by_id"
    )
    password_resets: Mapped[list["PasswordResetToken"]] = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )


__all__ = ["User"]
