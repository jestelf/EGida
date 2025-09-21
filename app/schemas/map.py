from __future__ import annotations

from typing import List

from pydantic import BaseModel

from app.schemas.graph import EdgeRead, NodeRead
from app.schemas.organization import SphereRead


class MapResponse(BaseModel):
    organization_id: int
    spheres: List[SphereRead]
    nodes: List[NodeRead]
    edges: List[EdgeRead]


__all__ = ["MapResponse"]
