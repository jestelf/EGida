from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import get_current_user, get_db
from app.models import Organization, OrganizationMember, OrganizationRole, User
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationMemberRead,
    OrganizationMemberUpdate,
    OrganizationRead,
)
from app.services import organizations as org_service

router = APIRouter()


@router.get("/", response_model=list[OrganizationRead])
def list_organizations(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[OrganizationRead]:
    organizations = session.scalars(
        select(Organization)
        .join(Organization.members)
        .where(OrganizationMember.user_id == current_user.id)
    ).all()
    return [OrganizationRead.model_validate(org) for org in organizations]


@router.post("/", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> OrganizationRead:
    organization = Organization(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        owner_id=current_user.id,
    )
    member = OrganizationMember(user_id=current_user.id, role=OrganizationRole.OWNER.value)
    organization.members.append(member)
    session.add(organization)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization already exists") from exc

    session.refresh(organization)
    return OrganizationRead.model_validate(organization)


@router.get("/{organization_id}", response_model=OrganizationRead)
def get_organization(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> OrganizationRead:
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    membership = org_service.get_membership(session, organization_id, current_user.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return OrganizationRead.model_validate(organization)


@router.get("/{organization_id}/members", response_model=list[OrganizationMemberRead])
def list_members(
    organization_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[OrganizationMemberRead]:
    org_service.require_membership(session, organization_id, current_user.id)

    members = session.scalars(
        select(OrganizationMember)
        .options(selectinload(OrganizationMember.user))
        .where(OrganizationMember.organization_id == organization_id)
        .order_by(OrganizationMember.created_at.asc())
    ).all()

    return [OrganizationMemberRead.model_validate(member) for member in members]


@router.patch("/{organization_id}/members/{member_id}", response_model=OrganizationMemberRead)
def update_member_role(
    organization_id: int,
    member_id: int,
    payload: OrganizationMemberUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> OrganizationMemberRead:
    acting_member = org_service.ensure_owner_or_admin(session, organization_id, current_user.id)

    member = session.get(OrganizationMember, member_id)
    if member is None or member.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    new_role = OrganizationRole(payload.role)
    updated = org_service.set_member_role(session, member, new_role, acting_member)
    session.refresh(updated, attribute_names=["user"])

    return OrganizationMemberRead.model_validate(updated)


@router.delete("/{organization_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def remove_member(
    organization_id: int,
    member_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    acting_member = org_service.ensure_owner_or_admin(session, organization_id, current_user.id)

    member = session.get(OrganizationMember, member_id)
    if member is None or member.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    member_role = OrganizationRole(member.role)
    acting_role = OrganizationRole(acting_member.role)

    if member_role == OrganizationRole.OWNER:
        owner_count = session.scalar(
            select(func.count())
            .select_from(OrganizationMember)
            .where(OrganizationMember.organization_id == organization_id)
            .where(OrganizationMember.role == OrganizationRole.OWNER.value)
        ) or 0
        if owner_count <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization must retain an owner")
        if acting_role != OrganizationRole.OWNER and member.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners can remove other owners")

    session.delete(member)
    session.commit()


