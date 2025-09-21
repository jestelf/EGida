from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

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
    organization_id: int = Field(
        validation_alias=AliasChoices("organization_id", "organizationId")
    )


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
    name: str = Field(validation_alias=AliasChoices("name", "label"))
    description: Optional[str] = None
    color: Optional[str] = None
    center_x: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("center_x", "centerX"),
    )
    center_y: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("center_y", "centerY"),
    )
    radius: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("radius", "sphereRadius"),
    )


class SphereCreate(SphereBase):
    organization_id: int = Field(
        validation_alias=AliasChoices("organization_id", "organizationId")
    )
    group_ids: List[int] = Field(
        default_factory=list, validation_alias=AliasChoices("group_ids", "groupIds")
    )


class SphereUpdate(BaseModel):
    name: Optional[str] = Field(default=None, validation_alias=AliasChoices("name", "label"))
    description: Optional[str] = None
    color: Optional[str] = None
    center_x: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("center_x", "centerX"),
    )
    center_y: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("center_y", "centerY"),
    )
    radius: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("radius", "sphereRadius"),
    )
    group_ids: Optional[List[int]] = Field(
        default=None, validation_alias=AliasChoices("group_ids", "groupIds")
    )


class SphereRead(SphereBase):
    id: int
    organization_id: int
    groups: List[GroupRead] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SphereLayoutItem(BaseModel):
    sphere_id: int = Field(validation_alias=AliasChoices("sphere_id", "sphereId"))
    center_x: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("center_x", "centerX"),
    )
    center_y: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("center_y", "centerY"),
    )
    radius: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        validation_alias=AliasChoices("radius", "sphereRadius"),
    )


class SphereLayoutRequest(BaseModel):
    organization_id: int = Field(
        validation_alias=AliasChoices("organization_id", "organizationId")
    )
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
