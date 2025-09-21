from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.models import Edge, Node, OrganizationMember, Sphere, User
from app.schemas.graph import (
    EDGE_TYPES,
    NODE_STATUSES,
    NODE_TYPES,
    EdgeCreate,
    EdgeRead,
    EdgeUpdate,
    GraphExportResponse,
    GraphImportPayload,
    GraphImportResult,
    NodeCreate,
    NodeRead,
    NodeUpdate,
)
from app.services import organizations as org_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_membership(session: Session, organization_id: int, user_id: int) -> None:
    membership = session.scalar(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.user_id == user_id)
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _get_sphere(session: Session, sphere_id: int, organization_id: Optional[int] = None) -> Sphere:
    sphere = session.get(Sphere, sphere_id)
    if sphere is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sphere not found")
    if organization_id is not None and sphere.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sphere outside organization")
    return sphere


def _validate_node_fields(node_type: Optional[str], status_value: Optional[str]) -> None:
    if node_type is not None and node_type not in NODE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid node type")
    if status_value is not None and status_value not in NODE_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid node status")


def _validate_edge_type(relation_type: Optional[str]) -> None:
    if relation_type is not None and relation_type not in EDGE_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid relation type")


@router.get("/nodes", response_model=List[NodeRead])
def list_nodes(
    organization_id: int = Query(..., description="Organization to scope the query"),
    sphere_id: Optional[int] = Query(None),
    node_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None, description="Search by label, summary, owners"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> List[NodeRead]:
    _ensure_membership(session, organization_id, current_user.id)
    _validate_node_fields(node_type, status_filter)

    query = select(Node).join(Sphere).where(Sphere.organization_id == organization_id)
    if sphere_id is not None:
        query = query.where(Node.sphere_id == sphere_id)
    if node_type is not None:
        query = query.where(Node.node_type == node_type)
    if status_filter is not None:
        query = query.where(Node.status == status_filter)
    if search:
        like = f"%{search.lower()}%"
        query = query.where(Node.label.ilike(like) | Node.summary.ilike(like))

    nodes = session.scalars(query.order_by(Node.created_at.desc())).all()
    return [NodeRead.model_validate(node) for node in nodes]


@router.post("/nodes", response_model=NodeRead, status_code=status.HTTP_201_CREATED)
def create_node(
    payload: NodeCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> NodeRead:
    sphere = _get_sphere(session, payload.sphere_id)
    _ensure_membership(session, sphere.organization_id, current_user.id)
    _validate_node_fields(payload.node_type, payload.status)

    node = Node(
        sphere_id=payload.sphere_id,
        label=payload.label,
        node_type=payload.node_type,
        status=payload.status,
        summary=payload.summary,
        position=payload.position,
        metadata_json=payload.metadata,
        links_json=payload.links,
        owners_json=payload.owners,
    )
    session.add(node)
    session.commit()
    session.refresh(node)
    logger.info("node.created", extra={"sphere_id": node.sphere_id, "node_id": node.id})
    return NodeRead.model_validate(node)


@router.patch("/nodes/{node_id}", response_model=NodeRead)
def update_node(
    node_id: int,
    payload: NodeUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> NodeRead:
    node = session.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    sphere = _get_sphere(session, node.sphere_id)
    _ensure_membership(session, sphere.organization_id, current_user.id)
    _validate_node_fields(payload.node_type, payload.status)

    if payload.label is not None:
        node.label = payload.label
    if payload.node_type is not None:
        node.node_type = payload.node_type
    if payload.status is not None:
        node.status = payload.status
    if payload.summary is not None:
        node.summary = payload.summary
    if payload.position is not None:
        node.position = payload.position
    if payload.metadata is not None:
        node.metadata_json = payload.metadata
    if payload.links is not None:
        node.links_json = payload.links
    if payload.owners is not None:
        node.owners_json = payload.owners

    session.add(node)
    session.commit()
    session.refresh(node)
    logger.info("node.updated", extra={"node_id": node.id})
    return NodeRead.model_validate(node)


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def delete_node(
    node_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    node = session.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    sphere = _get_sphere(session, node.sphere_id)
    _ensure_membership(session, sphere.organization_id, current_user.id)

    session.delete(node)
    session.commit()
    logger.info("node.deleted", extra={"node_id": node_id})


@router.get("/edges", response_model=List[EdgeRead])
def list_edges(
    organization_id: int = Query(..., description="Organization to scope the query"),
    sphere_id: Optional[int] = Query(None),
    relation_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> List[EdgeRead]:
    _ensure_membership(session, organization_id, current_user.id)
    _validate_edge_type(relation_type)

    query = select(Edge).join(Sphere).where(Sphere.organization_id == organization_id)
    if sphere_id is not None:
        query = query.where(Edge.sphere_id == sphere_id)
    if relation_type is not None:
        query = query.where(Edge.relation_type == relation_type)

    edges = session.scalars(query.order_by(Edge.created_at.desc())).all()
    return [EdgeRead.model_validate(edge) for edge in edges]


@router.post("/edges", response_model=EdgeRead, status_code=status.HTTP_201_CREATED)
def create_edge(
    payload: EdgeCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> EdgeRead:
    sphere = _get_sphere(session, payload.sphere_id)
    _ensure_membership(session, sphere.organization_id, current_user.id)
    _validate_edge_type(payload.relation_type)

    source = session.get(Node, payload.source_node_id)
    target = session.get(Node, payload.target_node_id)
    if not source or not target:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid node references")
    if source.sphere_id != sphere.id or target.sphere_id != sphere.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nodes must belong to the sphere")

    edge = Edge(
        sphere_id=payload.sphere_id,
        source_node_id=payload.source_node_id,
        target_node_id=payload.target_node_id,
        relation_type=payload.relation_type,
        metadata_json=payload.metadata,
    )
    session.add(edge)
    session.commit()
    session.refresh(edge)
    logger.info("edge.created", extra={"edge_id": edge.id, "sphere_id": edge.sphere_id})
    return EdgeRead.model_validate(edge)


@router.patch("/edges/{edge_id}", response_model=EdgeRead)
def update_edge(
    edge_id: int,
    payload: EdgeUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> EdgeRead:
    edge = session.get(Edge, edge_id)
    if edge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge not found")

    sphere = _get_sphere(session, edge.sphere_id)
    _ensure_membership(session, sphere.organization_id, current_user.id)
    _validate_edge_type(payload.relation_type)

    if payload.relation_type is not None:
        edge.relation_type = payload.relation_type
    if payload.metadata is not None:
        edge.metadata_json = payload.metadata

    session.add(edge)
    session.commit()
    session.refresh(edge)
    logger.info("edge.updated", extra={"edge_id": edge_id})
    return EdgeRead.model_validate(edge)


@router.delete("/edges/{edge_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def delete_edge(
    edge_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    edge = session.get(Edge, edge_id)
    if edge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge not found")

    sphere = _get_sphere(session, edge.sphere_id)
    _ensure_membership(session, sphere.organization_id, current_user.id)

    session.delete(edge)
    session.commit()
    logger.info("edge.deleted", extra={"edge_id": edge_id})


@router.get("/search", response_model=List[NodeRead])
def search_nodes(
    organization_id: int = Query(...),
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> List[NodeRead]:
    _ensure_membership(session, organization_id, current_user.id)
    like = f"%{q.lower()}%"
    query = (
        select(Node)
        .join(Sphere)
        .where(Sphere.organization_id == organization_id)
        .where(Node.label.ilike(like) | Node.summary.ilike(like))
        .order_by(Node.created_at.desc())
        .limit(20)
    )
    nodes = session.scalars(query).all()
    return [NodeRead.model_validate(node) for node in nodes]


@router.get("/export", response_model=GraphExportResponse)
def export_graph(
    organization_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> GraphExportResponse:
    _ensure_membership(session, organization_id, current_user.id)
    spheres = session.scalars(select(Sphere).where(Sphere.organization_id == organization_id)).all()
    sphere_ids = [sphere.id for sphere in spheres]
    nodes = session.scalars(select(Node).where(Node.sphere_id.in_(sphere_ids))).all()
    node_ids = [node.id for node in nodes]
    edges = session.scalars(select(Edge).where(Edge.source_node_id.in_(node_ids))).all()
    logger.info("graph.export", extra={"organization_id": organization_id, "nodes": len(nodes)})
    return GraphExportResponse(
        organization_id=organization_id,
        spheres=sphere_ids,
        nodes=[NodeRead.model_validate(node) for node in nodes],
        edges=[EdgeRead.model_validate(edge) for edge in edges],
    )


@router.post("/import", response_model=GraphImportResult)
def import_graph(
    payload: GraphImportPayload,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> GraphImportResult:
    org_service.ensure_owner_or_admin(session, payload.organization_id, current_user.id)
    spheres = session.scalars(select(Sphere).where(Sphere.organization_id == payload.organization_id)).all()
    sphere_ids = {sphere.id for sphere in spheres}

    # Prepare node mapping (old id -> Node instance)
    existing_nodes = session.scalars(
        select(Node)
        .join(Sphere)
        .where(Sphere.organization_id == payload.organization_id)
    ).all()
    existing_by_id = {node.id: node for node in existing_nodes}

    imported_nodes: List[Node] = []
    for node_data in payload.nodes or []:
        if node_data.sphere_id not in sphere_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Node sphere outside organization")
        node = existing_by_id.get(node_data.id)
        if node is None:
            node = Node(sphere_id=node_data.sphere_id)
        node.label = node_data.label
        node.node_type = node_data.node_type
        node.status = node_data.status
        node.summary = node_data.summary
        node.position = node_data.position
        node.metadata_json = node_data.metadata
        node.links_json = node_data.links
        node.owners_json = node_data.owners
        session.add(node)
        session.flush()
        imported_nodes.append(node)
        existing_by_id[node.id] = node

    node_id_map = {node.id: node.id for node in imported_nodes}

    # Remove edges for the organization prior to import and recreate
    session.execute(
        delete(Edge).where(
            Edge.sphere_id.in_(select(Sphere.id).where(Sphere.organization_id == payload.organization_id))
        )
    )

    imported_edges: List[Edge] = []
    for edge_data in payload.edges or []:
        if edge_data.sphere_id not in sphere_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Edge sphere outside organization")
        if edge_data.source_node_id not in node_id_map or edge_data.target_node_id not in node_id_map:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Edge references unknown node")
        edge = Edge(
            sphere_id=edge_data.sphere_id,
            source_node_id=edge_data.source_node_id,
            target_node_id=edge_data.target_node_id,
            relation_type=edge_data.relation_type,
            metadata_json=edge_data.metadata,
        )
        session.add(edge)
        imported_edges.append(edge)

    session.commit()
    logger.info(
        "graph.import", extra={"organization_id": payload.organization_id, "nodes": len(imported_nodes)}
    )
    refreshed_nodes = [NodeRead.model_validate(node) for node in imported_nodes]
    refreshed_edges = [EdgeRead.model_validate(edge) for edge in imported_edges]
    return GraphImportResult(nodes=refreshed_nodes, edges=refreshed_edges)



