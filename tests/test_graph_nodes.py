import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.routes import graph as graph_routes
from app.api.routes import spheres as spheres_routes
from app.db.base import Base
from app.models import Organization, OrganizationMember, OrganizationRole, Sphere
from app.schemas.graph import EdgeCreate, NodeCreate, NodeUpdate
from app.schemas.organization import SphereCreate
from app.schemas.user import UserCreate
from app.services import auth as auth_service


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, future=True)
    with TestingSessionLocal() as session:
        yield session


def bootstrap_org(session):
    owner = auth_service.register_user(session, UserCreate(email="owner.graph@example.com", password="secret123"))
    org = Organization(name="Graph Org", slug="graph-org", owner_id=owner.id)
    session.add(org)
    session.flush()
    membership = OrganizationMember(
        organization_id=org.id,
        user_id=owner.id,
        role=OrganizationRole.OWNER.value,
    )
    session.add(membership)
    sphere = Sphere(organization_id=org.id, name="Core", color="#38bdf8")
    session.add(sphere)
    session.commit()
    return owner, org, sphere


def test_node_and_edge_crud(session):
    owner, org, sphere = bootstrap_org(session)

    node_payload = NodeCreate(
        sphere_id=sphere.id,
        label="API Gateway",
        node_type="api",
        status="active",
        summary="Внешний шлюз",
        position={"x": 0.5, "y": 0.5},
        metadata={"stack": "fastapi"},
        links=["https://repo", "https://ci"],
        owners=["alice"],
    )
    created_node = graph_routes.create_node(node_payload, owner, session)
    assert created_node.node_type == "api"
    assert created_node.links == ["https://repo", "https://ci"]

    listed = graph_routes.list_nodes(
        organization_id=org.id,
        sphere_id=sphere.id,
        node_type="api",
        status_filter="active",
        current_user=owner,
        session=session,
    )
    assert len(listed) == 1

    update_payload = NodeUpdate.model_validate({"archived": True})
    updated_node = graph_routes.update_node(created_node.id, update_payload, owner, session)
    assert updated_node.status == "archived"

    node_payload_2 = NodeCreate.model_validate(
        {
            "sphereId": sphere.id,
            "name": "Event Bus",
            "nodeType": "event",
            "archived": False,
            "summary": "Событийная шина",
            "position": {"x": 0.6, "y": 0.6},
            "metadata": {},
            "links": "https://docs, https://status",
            "owners": ["bob"],
        }
    )
    created_node_2 = graph_routes.create_node(node_payload_2, owner, session)
    assert created_node_2.status == "active"
    assert created_node_2.links == ["https://docs", "https://status"]

    edge_payload = EdgeCreate.model_validate(
        {
            "sphereId": sphere.id,
            "sourceNodeId": created_node.id,
            "targetNodeId": created_node_2.id,
            "relationType": "uses",
            "metadata": {"note": "calls events"},
        }
    )
    created_edge = graph_routes.create_edge(edge_payload, owner, session)
    assert created_edge.relation_type == "uses"

    edges = graph_routes.list_edges(
        organization_id=org.id,
        sphere_id=sphere.id,
        relation_type=None,
        current_user=owner,
        session=session,
    )
    assert len(edges) == 1

    graph_routes.delete_edge(created_edge.id, owner, session)
    graph_routes.delete_node(created_node_2.id, owner, session)
    graph_routes.delete_node(created_node.id, owner, session)

    remaining_nodes = graph_routes.list_nodes(
        organization_id=org.id,
        sphere_id=None,
        node_type=None,
        status_filter=None,
        current_user=owner,
        session=session,
    )
    assert remaining_nodes == []


def test_sphere_create_accepts_camel_case_payload(session):
    owner, org, _ = bootstrap_org(session)

    payload = SphereCreate.model_validate(
        {
            "organizationId": org.id,
            "name": "Integration",
            "description": "Camel case payload",
            "color": "#112233",
            "centerX": 0.3,
            "centerY": 0.4,
            "radius": 0.25,
            "groupIds": [],
        }
    )

    created = spheres_routes.create_sphere(payload, owner, session)
    assert created.organization_id == org.id
    assert created.name == "Integration"
    assert created.center_x == 0.3
    assert created.center_y == 0.4
    assert created.radius == 0.25

