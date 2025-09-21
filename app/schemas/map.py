from __future__ import annotations

from typing import TYPE_CHECKING, List, Sequence

from pydantic import BaseModel, computed_field

from app.schemas.graph import EdgeRead, NodeRead
from app.schemas.organization import SphereRead

if TYPE_CHECKING:
    from app.models import Edge as EdgeModel, Node as NodeModel, Sphere as SphereModel


class MapNode(NodeRead):
    model_config = NodeRead.model_config

    @computed_field
    @property
    def name(self) -> str:
        return self.label

    @computed_field
    @property
    def kind(self) -> str:
        return self.node_type

    @computed_field
    @property
    def archived(self) -> bool:
        return self.status == "archived"

    @computed_field
    @property
    def x(self) -> float:
        return float(self.position.get("x", 0.0))

    @computed_field
    @property
    def y(self) -> float:
        return float(self.position.get("y", 0.0))


class MapEdge(EdgeRead):
    model_config = EdgeRead.model_config

    @computed_field
    @property
    def from_node_id(self) -> int:
        return self.source_node_id

    @computed_field
    @property
    def to_node_id(self) -> int:
        return self.target_node_id


class MapResponse(BaseModel):
    organization_id: int
    spheres: List[SphereRead]
    nodes: List[MapNode]
    edges: List[MapEdge]

    @classmethod
    def from_entities(
        cls,
        *,
        organization_id: int,
        spheres: Sequence["SphereModel"],
        nodes: Sequence["NodeModel"],
        edges: Sequence["EdgeModel"],
    ) -> "MapResponse":
        return cls(
            organization_id=organization_id,
            spheres=[SphereRead.model_validate(sphere) for sphere in spheres],
            nodes=[MapNode.model_validate(node) for node in nodes],
            edges=[MapEdge.model_validate(edge) for edge in edges],
        )


__all__ = ["MapNode", "MapEdge", "MapResponse"]
