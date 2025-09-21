from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.models import User
from app.models.organization import GroupMembership
from app.models.structures import Group
from app.schemas.organization import (
    GroupCreate,
    GroupMemberAdd,
    GroupMemberRead,
    GroupRead,
    GroupUpdate,
)
from app.services import organizations as org_service

router = APIRouter()


@router.get("/organizations/{organization_id}/groups", response_model=list[GroupRead])
def list_groups(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[GroupRead]:
    org_service.require_membership(session, organization_id, current_user.id)

    groups = session.scalars(
        select(Group)
        .options(selectinload(Group.memberships).selectinload(GroupMembership.user))
        .where(Group.organization_id == organization_id)
        .order_by(Group.created_at.asc())
    ).all()

    return [GroupRead.model_validate(group) for group in groups]


@router.post("/organizations/{organization_id}/groups", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create_group(
    organization_id: int,
    payload: GroupCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> GroupRead:
    org_service.ensure_owner_or_admin(session, organization_id, current_user.id)

    group = Group(
        organization_id=organization_id,
        name=payload.name,
        description=payload.description,
        color=payload.color,
    )
    session.add(group)
    session.commit()
    session.refresh(group)

    return GroupRead.model_validate(group)


@router.patch("/groups/{group_id}", response_model=GroupRead)
def update_group(
    group_id: int,
    payload: GroupUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> GroupRead:
    group = session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    org_service.ensure_owner_or_admin(session, group.organization_id, current_user.id)

    if payload.name is not None:
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description
    if payload.color is not None:
        group.color = payload.color

    session.add(group)
    session.commit()
    session.refresh(group)

    return GroupRead.model_validate(group)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def delete_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    group = session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    org_service.ensure_owner_or_admin(session, group.organization_id, current_user.id)

    session.delete(group)
    session.commit()


@router.post("/groups/{group_id}/members", response_model=GroupMemberRead, status_code=status.HTTP_201_CREATED)
def add_group_member(
    group_id: int,
    payload: GroupMemberAdd,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> GroupMemberRead:
    group = session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    org_service.ensure_owner_or_admin(session, group.organization_id, current_user.id)

    target_user = session.get(User, payload.user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    membership = org_service.add_user_to_group(session, group, target_user)
    session.refresh(membership, attribute_names=["user"])

    return GroupMemberRead.model_validate(membership)


@router.delete("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def remove_group_member(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    group = session.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    org_service.ensure_owner_or_admin(session, group.organization_id, current_user.id)

    target_user = session.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    org_service.remove_user_from_group(session, group, target_user)


