from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, get_db
from app.db.base import Base
from app.main import app
from app.models import Edge, Node, Organization, OrganizationMember, OrganizationRole, Sphere
from app.schemas.user import UserCreate
from app.services import auth as auth_service


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    try:
        with TestingSessionLocal() as session:
            yield session
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def map_test_data(session):
    owner = auth_service.register_user(
        session, UserCreate(email="owner.map@example.com", password="secret123")
    )

    organization = Organization(name="Map Org", slug="map-org", owner_id=owner.id)
    session.add(organization)
    session.flush()

    membership = OrganizationMember(
        organization_id=organization.id,
        user_id=owner.id,
        role=OrganizationRole.OWNER.value,
    )
    session.add(membership)

    primary_sphere = Sphere(organization_id=organization.id, name="Primary", color="#ff00ff")
    secondary_sphere = Sphere(organization_id=organization.id, name="Secondary", color="#00ff00")
    session.add_all([primary_sphere, secondary_sphere])
    session.flush()

    api_node = Node(
        sphere_id=primary_sphere.id,
        label="Payments API",
        node_type="api",
        status="active",
        summary="Processes external requests",
        position={"x": 0.1, "y": 0.2},
    )
    service_node = Node(
        sphere_id=primary_sphere.id,
        label="Billing Service",
        node_type="service",
        status="archived",
        summary="Legacy billing module",
        position={"x": 0.7, "y": 0.8},
    )
    event_node = Node(
        sphere_id=secondary_sphere.id,
        label="Event Gateway",
        node_type="event",
        status="active",
        summary="Publishes domain events",
        position={"x": 0.4, "y": 0.6},
    )
    session.add_all([api_node, service_node, event_node])
    session.flush()

    primary_edge = Edge(
        sphere_id=primary_sphere.id,
        source_node_id=api_node.id,
        target_node_id=service_node.id,
        relation_type="depends",
    )
    session.add(primary_edge)
    session.commit()

    for entity in [
        owner,
        organization,
        primary_sphere,
        secondary_sphere,
        api_node,
        service_node,
        event_node,
        primary_edge,
    ]:
        session.refresh(entity)

    return {
        "owner": owner,
        "organization": organization,
        "spheres": {
            "primary": primary_sphere,
            "secondary": secondary_sphere,
        },
        "nodes": {
            "api": api_node,
            "service": service_node,
            "event": event_node,
        },
        "edges": {"primary": primary_edge},
    }


@pytest.fixture()
def client(session, map_test_data):
    def override_get_db():
        yield session

    def override_get_current_user():
        return map_test_data["owner"]

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_map_route_returns_enhanced_payload(client: TestClient, map_test_data):
    org_id = map_test_data["organization"].id
    response = client.get("/api/map", params={"org_id": org_id})
    assert response.status_code == 200

    payload = response.json()
    assert payload["organization_id"] == org_id

    nodes_by_id = {node["id"]: node for node in payload["nodes"]}
    api_node = nodes_by_id[map_test_data["nodes"]["api"].id]
    service_node = nodes_by_id[map_test_data["nodes"]["service"].id]

    assert api_node["name"] == map_test_data["nodes"]["api"].label
    assert api_node["kind"] == map_test_data["nodes"]["api"].node_type
    assert api_node["archived"] is False
    assert api_node["x"] == pytest.approx(map_test_data["nodes"]["api"].position["x"])
    assert api_node["y"] == pytest.approx(map_test_data["nodes"]["api"].position["y"])

    assert service_node["archived"] is True

    assert payload["edges"]
    edge_payload = payload["edges"][0]
    assert edge_payload["from_node_id"] == map_test_data["nodes"]["api"].id
    assert edge_payload["to_node_id"] == map_test_data["nodes"]["service"].id


def test_map_route_filters_by_sphere(client: TestClient, map_test_data):
    org_id = map_test_data["organization"].id
    primary_id = map_test_data["spheres"]["primary"].id
    response = client.get("/api/map", params={"org_id": org_id, "sphere_id": primary_id})
    assert response.status_code == 200

    payload = response.json()
    node_ids = {node["id"] for node in payload["nodes"]}
    expected_ids = {
        map_test_data["nodes"]["api"].id,
        map_test_data["nodes"]["service"].id,
    }
    assert node_ids == expected_ids
    assert payload["edges"] and len(payload["edges"]) == 1


def test_map_route_filters_by_type(client: TestClient, map_test_data):
    org_id = map_test_data["organization"].id
    response = client.get(
        "/api/map",
        params={"org_id": org_id, "type": map_test_data["nodes"]["service"].node_type},
    )
    assert response.status_code == 200

    payload = response.json()
    node_ids = {node["id"] for node in payload["nodes"]}
    assert node_ids == {map_test_data["nodes"]["service"].id}
    assert payload["edges"] == []


def test_map_route_filters_by_status(client: TestClient, map_test_data):
    org_id = map_test_data["organization"].id
    response = client.get("/api/map", params={"org_id": org_id, "status": "archived"})
    assert response.status_code == 200

    payload = response.json()
    node_ids = {node["id"] for node in payload["nodes"]}
    assert node_ids == {map_test_data["nodes"]["service"].id}
    assert payload["nodes"][0]["archived"] is True


def test_map_route_filters_by_search(client: TestClient, map_test_data):
    org_id = map_test_data["organization"].id
    response = client.get(
        "/api/map",
        params={"org_id": org_id, "search": "  LEGACY  "},
    )
    assert response.status_code == 200

    payload = response.json()
    node_ids = {node["id"] for node in payload["nodes"]}
    assert node_ids == {map_test_data["nodes"]["service"].id}
