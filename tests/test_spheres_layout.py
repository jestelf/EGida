import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models import Organization, OrganizationMember, OrganizationRole, Sphere
from app.schemas.organization import SphereLayoutRequest
from app.schemas.user import UserCreate
from app.services import auth as auth_service


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, future=True)
    with TestingSessionLocal() as session:
        yield session


def create_org(session):
    owner = auth_service.register_user(session, UserCreate(email="owner.spheres@example.com", password="secret123"))
    org = Organization(name="Layout Org", slug="layout-org", owner_id=owner.id)
    session.add(org)
    session.flush()
    session.add(
        OrganizationMember(
            organization_id=org.id,
            user_id=owner.id,
            role=OrganizationRole.OWNER.value,
        )
    )
    session.commit()
    return owner, org


def test_sphere_layout_update(session):
    owner, org = create_org(session)

    sphere_a = Sphere(organization_id=org.id, name="Alpha", color="#38bdf8")
    sphere_b = Sphere(organization_id=org.id, name="Beta", color="#fb923c")
    session.add_all([sphere_a, sphere_b])
    session.commit()

    layout_payload = SphereLayoutRequest(
        organization_id=org.id,
        layout=[
            {"sphere_id": sphere_a.id, "center_x": 0.4, "center_y": 0.6, "radius": 0.2},
            {"sphere_id": sphere_b.id, "center_x": 0.7, "center_y": 0.3, "radius": 0.18},
        ],
    )

    from app.api.routes import spheres as spheres_routes

    updated = spheres_routes.update_sphere_layout(layout_payload, owner, session)

    assert len(updated) == 2
    updated_a = next(item for item in updated if item.id == sphere_a.id)
    assert updated_a.center_x == pytest.approx(0.4)
    assert updated_a.center_y == pytest.approx(0.6)
    assert updated_a.radius == pytest.approx(0.2)

    persisted = session.scalar(select(Sphere).where(Sphere.id == sphere_b.id))
    assert persisted.center_x == pytest.approx(0.7)
    assert persisted.radius == pytest.approx(0.18)


