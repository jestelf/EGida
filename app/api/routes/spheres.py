from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_db
from app.models import Group, Sphere, User
from app.schemas.organization import (
    SphereCreate,
    SphereLayoutRequest,
    SphereRead,
    SphereUpdate,
)
from app.services import organizations as org_service

router = APIRouter()

_DEFAULT_RADIUS = 0.22


def _get_sphere(session: Session, sphere_id: int) -> Sphere:
    sphere = session.get(Sphere, sphere_id)
    if sphere is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sphere not found")
    return sphere


@router.get("/", response_model=List[SphereRead])
def list_spheres(
    organization_id: int = Query(..., description="Filter spheres by organization"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> List[SphereRead]:
    org_service.require_membership(session, organization_id, current_user.id)

    spheres = (
        session.scalars(
            select(Sphere)
            .options(selectinload(Sphere.groups))
            .where(Sphere.organization_id == organization_id)
            .order_by(Sphere.created_at.desc())
        )
        .unique()
        .all()
    )
    return [SphereRead.model_validate(sphere) for sphere in spheres]


@router.post("/", response_model=SphereRead, status_code=status.HTTP_201_CREATED)
def create_sphere(
    payload: SphereCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> SphereRead:
    org_service.ensure_owner_or_admin(session, payload.organization_id, current_user.id)

    sphere = Sphere(
        organization_id=payload.organization_id,
        name=payload.name,
        description=payload.description,
        color=payload.color,
        center_x=payload.center_x,
        center_y=payload.center_y,
        radius=payload.radius if payload.radius is not None else _DEFAULT_RADIUS,
    )

    if payload.group_ids:
        groups = session.scalars(
            select(Group)
            .where(Group.organization_id == payload.organization_id)
            .where(Group.id.in_(payload.group_ids))
        ).all()
        if len(groups) != len(set(payload.group_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group mapping")
        sphere.groups.extend(groups)

    session.add(sphere)
    session.commit()
    session.refresh(sphere)

    return SphereRead.model_validate(sphere)


@router.get("/{sphere_id}", response_model=SphereRead)
def get_sphere(
    sphere_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> SphereRead:
    sphere = _get_sphere(session, sphere_id)
    org_service.require_membership(session, sphere.organization_id, current_user.id)
    return SphereRead.model_validate(sphere)


@router.patch("/{sphere_id}", response_model=SphereRead)
def update_sphere(
    sphere_id: int,
    payload: SphereUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> SphereRead:
    sphere = _get_sphere(session, sphere_id)
    org_service.ensure_owner_or_admin(session, sphere.organization_id, current_user.id)

    if payload.name is not None:
        sphere.name = payload.name
    if payload.description is not None:
        sphere.description = payload.description
    if payload.color is not None:
        sphere.color = payload.color
    if payload.center_x is not None:
        sphere.center_x = payload.center_x
    if payload.center_y is not None:
        sphere.center_y = payload.center_y
    if payload.radius is not None:
        sphere.radius = payload.radius

    if payload.group_ids is not None:
        groups = session.scalars(
            select(Group)
            .where(Group.organization_id == sphere.organization_id)
            .where(Group.id.in_(payload.group_ids))
        ).all()
        if len(groups) != len(set(payload.group_ids)):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group mapping")
        sphere.groups = groups

    session.add(sphere)
    session.commit()
    session.refresh(sphere)

    return SphereRead.model_validate(sphere)


@router.post("/layout", response_model=List[SphereRead])
def update_sphere_layout(
    payload: SphereLayoutRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> List[SphereRead]:
    org_service.ensure_owner_or_admin(session, payload.organization_id, current_user.id)

    layout_map = {item.sphere_id: item for item in payload.layout}
    if not layout_map:
        return []

    spheres = session.scalars(
        select(Sphere)
        .options(selectinload(Sphere.groups))
        .where(Sphere.id.in_(layout_map.keys()))
    ).all()

    if len(spheres) != len(layout_map):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sphere set mismatch")

    for sphere in spheres:
        if sphere.organization_id != payload.organization_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sphere outside organization")
        update = layout_map[sphere.id]
        if update.center_x is not None:
            sphere.center_x = update.center_x
        if update.center_y is not None:
            sphere.center_y = update.center_y
        if update.radius is not None:
            sphere.radius = update.radius
        session.add(sphere)

    session.commit()

    # Refresh to include relationships
    for sphere in spheres:
        session.refresh(sphere)

    return [SphereRead.model_validate(sphere) for sphere in spheres]



