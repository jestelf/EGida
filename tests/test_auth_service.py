import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.security import verify_password
from app.db.base import Base
from app.models import GroupMembership, InviteStatus, Organization, OrganizationMember, OrganizationRole, User
from app.models.structures import Group
from app.schemas.invite import InviteCreate
from app.schemas.user import UserCreate
from app.services import auth as auth_service
from app.services import invites as invite_service
from app.services import organizations as org_service


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, future=True)
    with TestingSessionLocal() as session:
        yield session


def test_password_reset_flow(session):
    user = auth_service.register_user(session, UserCreate(email="reset@example.com", password="oldpass123"))

    token_data = auth_service.request_password_reset(session, user.email)
    assert token_data is not None
    token, expires_at = token_data
    assert token

    auth_service.reset_password(session, token, "newpass456")

    refreshed = session.get(User, user.id)
    assert refreshed is not None
    assert verify_password("newpass456", refreshed.hashed_password)
    assert not verify_password("oldpass123", refreshed.hashed_password)


def test_invite_flow_assigns_membership_and_groups(session):
    owner = auth_service.register_user(session, UserCreate(email="owner@example.com", password="secret123"))
    org = Organization(name="Demo Org", slug="demo-org", owner_id=owner.id)
    session.add(org)
    session.flush()

    session.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=owner.id,
            role=OrganizationRole.OWNER.value,
        )
    )
    group = Group(organization_id=org.id, name="Backend")
    session.add(group)
    session.commit()

    invitee = auth_service.register_user(session, UserCreate(email="member@example.com", password="passwd123"))

    invite, token, _ = invite_service.create_invite(
        session,
        InviteCreate(organization_id=org.id, email=invitee.email, group_ids=[group.id]),
        inviter=owner,
    )

    accepted_invite = invite_service.accept_invite(session, token, invitee)
    assert accepted_invite.status == InviteStatus.ACCEPTED

    membership = org_service.get_membership(session, org.id, invitee.id)
    assert membership is not None
    assert membership.role == OrganizationRole.MEMBER.value

    group_membership = session.scalar(
        select(GroupMembership)
        .where(GroupMembership.group_id == group.id)
        .where(GroupMembership.user_id == invitee.id)
    )
    assert group_membership is not None


