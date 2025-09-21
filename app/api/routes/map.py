from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AliasChoices
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.models import Edge, Node, Sphere, User
from app.schemas.graph import NODE_STATUSES, NODE_TYPES
from app.schemas.map import MapResponse
from app.services import organizations as org_service

router = APIRouter()


def _validate_filters(node_type: Optional[str], status_value: Optional[str]) -> None:
    if node_type is not None and node_type not in NODE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid node type")
    if status_value is not None and status_value not in NODE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid node status")


@router.get("/", response_model=MapResponse)
def read_map(
    organization_id: int = Query(
        ...,
        alias="org_id",
        validation_alias=AliasChoices("organization_id", "org_id"),
        description="Organization identifier",
    ),
    sphere_id: Optional[int] = Query(None, description="Limit nodes to a sphere"),
    node_type: Optional[str] = Query(
        None,
        alias="type",
        validation_alias=AliasChoices("node_type", "type"),
        description="Filter by node type",
    ),
    status_value: Optional[str] = Query(
        None,
        alias="status",
        validation_alias=AliasChoices("status_value", "status"),
        description="Filter by node status",
    ),
    search: Optional[str] = Query(None, description="Case-insensitive search by label or summary"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> MapResponse:
    org_service.require_membership(session, organization_id, current_user.id)
    _validate_filters(node_type, status_value)

    spheres_query = (
        select(Sphere)
        .where(Sphere.organization_id == organization_id)
        .options(selectinload(Sphere.groups)).order_by(Sphere.created_at.asc())
    )
    spheres = session.scalars(spheres_query).all()

    if sphere_id is not None:
        if not any(sphere.id == sphere_id for sphere in spheres):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sphere outside organization")

    node_query = (
        select(Node)
        .join(Sphere)
        .where(Sphere.organization_id == organization_id)
    )
    if sphere_id is not None:
        node_query = node_query.where(Node.sphere_id == sphere_id)
    if node_type is not None:
        node_query = node_query.where(Node.node_type == node_type)
    if status_value is not None:
        node_query = node_query.where(Node.status == status_value)
    search_value: Optional[str]
    if isinstance(search, str):
        search_value = search.strip().lower()
    else:
        search_value = None
    if search_value:
        like = f"%{search_value}%"
        node_query = node_query.where(Node.label.ilike(like) | Node.summary.ilike(like))

    nodes = session.scalars(node_query.order_by(Node.created_at.desc())).all()
    node_ids = [node.id for node in nodes]

    edges: list[Edge]
    if not node_ids:
        edges = []
    else:
        edge_query = (
            select(Edge)
            .join(Sphere)
            .where(Sphere.organization_id == organization_id)
        )
        if sphere_id is not None:
            edge_query = edge_query.where(Edge.sphere_id == sphere_id)
        edge_query = edge_query.where(Edge.source_node_id.in_(node_ids)).where(Edge.target_node_id.in_(node_ids))
        edges = session.scalars(edge_query).all()

    return MapResponse.from_entities(
        organization_id=organization_id,
        spheres=spheres,
        nodes=nodes,
        edges=edges,
    )
