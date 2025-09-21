from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import InviteStatus
from app.models.organization import OrganizationRole
from app.schemas.organization import UserSummary


class InviteCreate(BaseModel):
    organization_id: int
    email: EmailStr
    role: OrganizationRole = OrganizationRole.MEMBER
    group_ids: List[int] = Field(default_factory=list)
    expires_in_hours: int = Field(default=72, ge=1, le=24 * 14)


class InviteRead(BaseModel):
    id: int
    email: EmailStr
    role: OrganizationRole
    group_ids: List[int]
    status: InviteStatus
    created_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    invited_by: Optional[UserSummary] = None

    model_config = ConfigDict(from_attributes=True)


class InviteAccept(BaseModel):
    token: str


class InvitePreview(BaseModel):
    organization_id: int
    email: EmailStr
    role: OrganizationRole
    group_ids: List[int]
    expires_at: datetime
    status: InviteStatus

    model_config = ConfigDict(from_attributes=True)


class InviteCreateResponse(BaseModel):
    invite: InviteRead
    invite_link: str
    token: Optional[str] = None


__all__ = [
    "InviteCreate",
    "InviteRead",
    "InviteAccept",
    "InvitePreview",
    "InviteCreateResponse",
]
