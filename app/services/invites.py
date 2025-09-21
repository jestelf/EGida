from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import List, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import InviteStatus, OrganizationInvite, OrganizationMember, OrganizationRole, User
from app.schemas.invite import InviteCreate
from app.services import organizations as org_service

_INVITE_EXPIRES_DEFAULT = timedelta(hours=72)


def _hash_token(token: str) -> str:
    import hashlib

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validate_role_for_inviter(inviter_role: OrganizationRole, requested_role: OrganizationRole) -> None:
    if inviter_role == OrganizationRole.ADMIN and requested_role == OrganizationRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins cannot invite owners")


def create_invite(
    session: Session,
    payload: InviteCreate,
    inviter: User,
) -> Tuple[OrganizationInvite, str, List[str]]:
    organization = org_service.fetch_organization(session, payload.organization_id)
    inviter_membership = org_service.ensure_owner_or_admin(session, organization.id, inviter.id)

    requested_role = OrganizationRole(payload.role)
    inviter_role = OrganizationRole(inviter_membership.role)
    _validate_role_for_inviter(inviter_role, requested_role)

    groups = org_service.validate_group_ids(session, organization.id, payload.group_ids)

    expires_delta = timedelta(hours=payload.expires_in_hours) if payload.expires_in_hours else _INVITE_EXPIRES_DEFAULT
    now = datetime.utcnow()

    raw_token = secrets.token_urlsafe(48)
    invite = OrganizationInvite(
        organization_id=organization.id,
        invited_by_id=inviter.id,
        email=payload.email,
        role=requested_role.value,
        group_ids=payload.group_ids,
        token_hash=_hash_token(raw_token),
        expires_at=now + expires_delta,
    )

    session.add(invite)
    session.commit()
    session.refresh(invite)
    session.refresh(invite, attribute_names=["organization", "invited_by"])

    return invite, raw_token, [group.name for group in groups]


def list_invites(session: Session, organization_id: int) -> list[OrganizationInvite]:
    return session.scalars(
        select(OrganizationInvite)
        .options(selectinload(OrganizationInvite.invited_by))
        .where(OrganizationInvite.organization_id == organization_id)
        .order_by(OrganizationInvite.created_at.desc())
    ).all()


def get_invite_by_token(session: Session, token: str) -> OrganizationInvite | None:
    hashed = _hash_token(token)
    return session.scalar(select(OrganizationInvite).where(OrganizationInvite.token_hash == hashed))


def ensure_invite_active(session: Session, invite: OrganizationInvite) -> None:
    now = datetime.utcnow()
    if invite.status == InviteStatus.REVOKED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite revoked")
    if invite.status == InviteStatus.ACCEPTED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite already accepted")
    if invite.expires_at <= now:
        invite.status = InviteStatus.EXPIRED
        session.add(invite)
        session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite expired")


def accept_invite(session: Session, token: str, user: User) -> OrganizationInvite:
    invite = get_invite_by_token(session, token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite token")

    ensure_invite_active(session, invite)

    if invite.email.lower() != user.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite email mismatch")

    if org_service.get_membership(session, invite.organization_id, user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already joined organization")

    membership = OrganizationMember(
        organization_id=invite.organization_id,
        user_id=user.id,
        role=invite.role,
    )
    session.add(membership)
    session.commit()
    session.refresh(membership)

    org_service.link_user_to_groups(session, user, invite.organization_id, invite.group_ids)

    invite.status = InviteStatus.ACCEPTED
    invite.accepted_at = datetime.utcnow()
    invite.accepted_by_id = user.id
    session.add(invite)
    session.commit()
    session.refresh(invite)
    session.refresh(invite, attribute_names=["organization", "invited_by"])

    return invite


def build_invite_link(token: str) -> str:
    base_url = settings.app_base_url.rstrip("/")
    return f"{base_url}/invite/accept?token={token}"
