from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models import InviteStatus, OrganizationInvite, User
from app.schemas.invite import InviteAccept, InviteCreate, InviteCreateResponse, InviteRead
from app.services import email as email_service
from app.services import invites as invite_service
from app.services import organizations as org_service

router = APIRouter()


@router.get("/", response_model=list[InviteRead])
def list_invites(
    organization_id: int = Query(..., description="Organization identifier"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[InviteRead]:
    org_service.ensure_owner_or_admin(session, organization_id, current_user.id)
    invites = invite_service.list_invites(session, organization_id)
    return [InviteRead.model_validate(invite) for invite in invites]


@router.post("/", response_model=InviteCreateResponse, status_code=status.HTTP_201_CREATED)
def create_invite(
    payload: InviteCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> InviteCreateResponse:
    invite, token, group_names = invite_service.create_invite(session, payload, current_user)
    invite_link = invite_service.build_invite_link(token)

    email_package = email_service.prepare_invite_email(
        project_name=settings.project_name,
        organization_name=invite.organization.name,
        inviter_email=current_user.email,
        invitee_email=invite.email,
        invite_link=invite_link,
        role=invite.role,
        group_names=group_names,
        expires_at=invite.expires_at.isoformat(),
    )
    email_service.log_email(email_package)

    response = InviteCreateResponse(
        invite=InviteRead.model_validate(invite),
        invite_link=invite_link,
        token=token if settings.debug else None,
    )
    return response


@router.post("/accept", response_model=InviteRead)
def accept_invite(
    payload: InviteAccept,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> InviteRead:
    membership = invite_service.accept_invite(session, payload.token, current_user)
    invite = invite_service.get_invite_by_token(session, payload.token)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite no longer available")
    return InviteRead.model_validate(invite)


@router.post("/{invite_id}/revoke", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def revoke_invite(
    invite_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    invite = session.get(OrganizationInvite, invite_id)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    org_service.ensure_owner_or_admin(session, invite.organization_id, current_user.id)

    if invite.status != InviteStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite cannot be revoked")

    invite.status = InviteStatus.REVOKED
    session.add(invite)
    session.commit()



