from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.routes import graph as graph_routes
from app.models import User
from app.schemas.graph import NodeCreate, NodeRead, NodeUpdate

router = APIRouter()


@router.post("/", response_model=NodeRead, status_code=status.HTTP_201_CREATED)
def create_node(
    payload: NodeCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> NodeRead:
    return graph_routes.create_node(payload, current_user, session)


@router.patch("/{node_id}", response_model=NodeRead)
def update_node(
    node_id: int,
    payload: NodeUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> NodeRead:
    return graph_routes.update_node(node_id, payload, current_user, session)


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def delete_node(
    node_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    graph_routes.delete_node(node_id, current_user, session)
    return None
