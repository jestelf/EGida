from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Group,
    GroupMembership,
    InviteStatus,
    Organization,
    OrganizationInvite,
    OrganizationMember,
    OrganizationRole,
    User,
)


def get_membership(session: Session, organization_id: int, user_id: int) -> OrganizationMember | None:
    return session.scalar(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.user_id == user_id)
    )


def require_membership(
    session: Session,
    organization_id: int,
    user_id: int,
    roles: Iterable[OrganizationRole] | None = None,
) -> OrganizationMember:
    membership = get_membership(session, organization_id, user_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    if roles is not None and OrganizationRole(membership.role) not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")

    return membership


def ensure_owner_or_admin(session: Session, organization_id: int, user_id: int) -> OrganizationMember:
    return require_membership(
        session,
        organization_id,
        user_id,
        roles=(OrganizationRole.OWNER, OrganizationRole.ADMIN),
    )


def set_member_role(
    session: Session,
    member: OrganizationMember,
    new_role: OrganizationRole,
    acting_member: OrganizationMember,
) -> OrganizationMember:
    current_role = OrganizationRole(member.role)

    acting_role = OrganizationRole(acting_member.role)
    if acting_role == OrganizationRole.ADMIN and current_role == OrganizationRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins cannot modify owners")

    if current_role == OrganizationRole.OWNER and new_role != OrganizationRole.OWNER:
        owner_count = session.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(OrganizationMember.organization_id == member.organization_id)
            .where(OrganizationMember.role == OrganizationRole.OWNER.value)
        ) or 0
        if owner_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization must have an owner")

    member.role = new_role.value
    session.add(member)
    session.commit()
    session.refresh(member)
    return member


def validate_group_ids(
    session: Session,
    organization_id: int,
    group_ids: list[int],
) -> list[Group]:
    if not group_ids:
        return []

    groups = session.scalars(select(Group).where(Group.id.in_(group_ids))).all()
    existing_ids = {group.id for group in groups}
    missing = set(group_ids) - existing_ids
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group IDs")

    for group in groups:
        if group.organization_id != organization_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group outside organization")

    return groups


def add_user_to_group(session: Session, group: Group, user: User) -> GroupMembership:
    if get_membership(session, group.organization_id, user.id) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User must belong to the organization")

    membership = session.scalar(
        select(GroupMembership)
        .where(GroupMembership.group_id == group.id)
        .where(GroupMembership.user_id == user.id)
    )
    if membership:
        return membership

    membership = GroupMembership(
        organization_id=group.organization_id,
        group_id=group.id,
        user_id=user.id,
    )
    session.add(membership)
    session.commit()
    session.refresh(membership)
    return membership


def remove_user_from_group(session: Session, group: Group, user: User) -> None:
    membership = session.scalar(
        select(GroupMembership)
        .where(GroupMembership.group_id == group.id)
        .where(GroupMembership.user_id == user.id)
    )
    if membership is None:
        return

    session.delete(membership)
    session.commit()


def link_user_to_groups(
    session: Session,
    user: User,
    organization_id: int,
    group_ids: list[int],
) -> None:
    groups = validate_group_ids(session, organization_id, group_ids)
    for group in groups:
        add_user_to_group(session, group, user)


def fetch_organization(session: Session, organization_id: int) -> Organization:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


def revoke_invite(session: Session, invite: OrganizationInvite) -> None:
    invite.status = InviteStatus.REVOKED
    session.add(invite)
    session.commit()
