from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.organization import OrganizationRole


class UserSummary(BaseModel):
    id: int
    email: str

    model_config = ConfigDict(from_attributes=True)


class OrganizationBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationRead(OrganizationBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrganizationMemberRead(BaseModel):
    id: int
    role: OrganizationRole
    created_at: datetime
    user: UserSummary

    model_config = ConfigDict(from_attributes=True)


class OrganizationMemberUpdate(BaseModel):
    role: OrganizationRole


class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None


class GroupCreate(GroupBase):
    organization_id: int


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class GroupMemberRead(BaseModel):
    id: int
    created_at: datetime
    user: UserSummary

    model_config = ConfigDict(from_attributes=True)


class GroupMemberAdd(BaseModel):
    user_id: int


class GroupRead(GroupBase):
    id: int
    organization_id: int
    created_at: datetime
    members: List[GroupMemberRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SphereBase(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    center_x: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    center_y: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    radius: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class SphereCreate(SphereBase):
    organization_id: int
    group_ids: List[int] = Field(default_factory=list)


class SphereUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    center_x: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    center_y: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    radius: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    group_ids: Optional[List[int]] = None


class SphereRead(SphereBase):
    id: int
    organization_id: int
    groups: List[GroupRead] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SphereLayoutItem(BaseModel):
    sphere_id: int
    center_x: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    center_y: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    radius: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class SphereLayoutRequest(BaseModel):
    organization_id: int
    layout: List[SphereLayoutItem]


__all__ = [
    "OrganizationBase",
    "OrganizationCreate",
    "OrganizationRead",
    "OrganizationMemberRead",
    "OrganizationMemberUpdate",
    "GroupBase",
    "GroupCreate",
    "GroupUpdate",
    "GroupRead",
    "GroupMemberRead",
    "GroupMemberAdd",
    "SphereBase",
    "SphereCreate",
    "SphereUpdate",
    "SphereRead",
    "SphereLayoutItem",
    "SphereLayoutRequest",
    "OrganizationRole",
]
