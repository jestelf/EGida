from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.routes import graph as graph_routes
from app.models import User
from app.schemas.graph import EdgeCreate, EdgeRead, EdgeUpdate

router = APIRouter()


@router.post("/", response_model=EdgeRead, status_code=status.HTTP_201_CREATED)
def create_edge(
    payload: EdgeCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> EdgeRead:
    return graph_routes.create_edge(payload, current_user, session)


@router.patch("/{edge_id}", response_model=EdgeRead)
def update_edge(
    edge_id: int,
    payload: EdgeUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> EdgeRead:
    return graph_routes.update_edge(edge_id, payload, current_user, session)


@router.delete("/{edge_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response, response_model=None)
def delete_edge(
    edge_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> None:
    graph_routes.delete_edge(edge_id, current_user, session)
    return None
