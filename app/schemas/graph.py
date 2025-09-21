from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

NODE_TYPES = {"api", "event", "service", "ui", "store", "task"}
NODE_STATUSES = {"active", "archived"}
EDGE_TYPES = {"uses", "produces", "consumes", "depends"}


class NodeBase(BaseModel):
    label: str = Field(validation_alias=AliasChoices("label", "name"))
    node_type: str = Field(default="service", validation_alias=AliasChoices("node_type", "nodeType"))
    status: str = Field(default="active")
    summary: Optional[str] = None
    position: Dict[str, float]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    links: List[str] = Field(default_factory=list)
    owners: List[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def apply_archived_flag(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        archived_value: Any = None
        if "archived" in data:
            archived_value = data.pop("archived")
        elif "is_archived" in data:
            archived_value = data.pop("is_archived")
        elif "isArchived" in data:
            archived_value = data.pop("isArchived")

        if archived_value is None:
            return data

        archived_bool: Optional[bool]
        if isinstance(archived_value, bool):
            archived_bool = archived_value
        elif isinstance(archived_value, (int, float)):
            archived_bool = bool(archived_value)
        elif isinstance(archived_value, str):
            lowered = archived_value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                archived_bool = True
            elif lowered in {"false", "0", "no", "off", ""}:
                archived_bool = False
            else:
                raise ValueError("invalid archived flag")
        else:
            raise ValueError("invalid archived flag")

        derived_status = "archived" if archived_bool else "active"
        existing_status = data.get("status")
        if existing_status is not None and existing_status != derived_status:
            raise ValueError("conflicting archived flag and status")
        data["status"] = derived_status
        return data

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, value: str) -> str:
        if value not in NODE_TYPES:
            raise ValueError("invalid node type")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in NODE_STATUSES:
            raise ValueError("invalid node status")
        return value

    @field_validator("position")
    @classmethod
    def normalize_position(cls, value: Dict[str, float]) -> Dict[str, float]:
        return {"x": float(value.get("x", 0.5)), "y": float(value.get("y", 0.5))}

    @field_validator("links", mode="before")
    @classmethod
    def split_links(cls, value: List[str] | str) -> List[str]:
        if isinstance(value, str):
            value = [part.strip() for part in value.split(",") if part.strip()]
        return [item.strip() for item in value or []]

    @field_validator("owners", mode="before")
    @classmethod
    def split_owners(cls, value: List[str] | str) -> List[str]:
        if isinstance(value, str):
            value = [part.strip() for part in value.split(",") if part.strip()]
        return [item.strip() for item in value or []]


class NodeCreate(NodeBase):
    sphere_id: int = Field(validation_alias=AliasChoices("sphere_id", "sphereId"))


class NodeUpdate(BaseModel):
    label: Optional[str] = Field(default=None, validation_alias=AliasChoices("label", "name"))
    node_type: Optional[str] = Field(default=None, validation_alias=AliasChoices("node_type", "nodeType"))
    status: Optional[str] = None
    summary: Optional[str] = None
    position: Optional[Dict[str, float]] = None
    metadata: Optional[Dict[str, Any]] = None
    links: Optional[List[str]] = None
    owners: Optional[List[str]] = None

    @model_validator(mode="before")
    @classmethod
    def apply_archived_flag(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        archived_value: Any = None
        if "archived" in data:
            archived_value = data.pop("archived")
        elif "is_archived" in data:
            archived_value = data.pop("is_archived")
        elif "isArchived" in data:
            archived_value = data.pop("isArchived")

        if archived_value is None:
            return data

        if isinstance(archived_value, bool):
            archived_bool = archived_value
        elif isinstance(archived_value, (int, float)):
            archived_bool = bool(archived_value)
        elif isinstance(archived_value, str):
            lowered = archived_value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                archived_bool = True
            elif lowered in {"false", "0", "no", "off", ""}:
                archived_bool = False
            else:
                raise ValueError("invalid archived flag")
        else:
            raise ValueError("invalid archived flag")

        derived_status = "archived" if archived_bool else "active"
        existing_status = data.get("status")
        if existing_status is not None and existing_status != derived_status:
            raise ValueError("conflicting archived flag and status")
        data["status"] = derived_status
        return data

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in NODE_TYPES:
            raise ValueError("invalid node type")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in NODE_STATUSES:
            raise ValueError("invalid node status")
        return value

    @field_validator("links", mode="before")
    @classmethod
    def split_links(cls, value: List[str] | str | None) -> Optional[List[str]]:
        if value is None:
            return value
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return [item.strip() for item in value]

    @field_validator("owners", mode="before")
    @classmethod
    def split_owners(cls, value: List[str] | str | None) -> Optional[List[str]]:
        if value is None:
            return value
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return [item.strip() for item in value]


class NodeRead(NodeBase):
    id: int
    sphere_id: int
    created_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_json")
    links: List[str] = Field(default_factory=list, alias="links_json")
    owners: List[str] = Field(default_factory=list, alias="owners_json")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class EdgeBase(BaseModel):
    sphere_id: int = Field(validation_alias=AliasChoices("sphere_id", "sphereId"))
    source_node_id: int = Field(validation_alias=AliasChoices("source_node_id", "sourceNodeId"))
    target_node_id: int = Field(validation_alias=AliasChoices("target_node_id", "targetNodeId"))
    relation_type: str = Field(default="depends", validation_alias=AliasChoices("relation_type", "relationType"))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("relation_type")
    @classmethod
    def validate_relation(cls, value: str) -> str:
        if value not in EDGE_TYPES:
            raise ValueError("invalid relation type")
        return value


class EdgeCreate(EdgeBase):
    pass


class EdgeUpdate(BaseModel):
    relation_type: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("relation_type", "relationType")
    )
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("relation_type")
    @classmethod
    def validate_relation(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in EDGE_TYPES:
            raise ValueError("invalid relation type")
        return value


class EdgeRead(BaseModel):
    id: int
    sphere_id: int
    source_node_id: int
    target_node_id: int
    relation_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="metadata_json")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class GraphExportResponse(BaseModel):
    organization_id: int
    spheres: List[int]
    nodes: List[NodeRead]
    edges: List[EdgeRead]


class GraphImportPayload(BaseModel):
    organization_id: int
    nodes: Optional[List[NodeRead]] = None
    edges: Optional[List[EdgeRead]] = None


class GraphImportResult(BaseModel):
    nodes: List[NodeRead]
    edges: List[EdgeRead]


__all__ = [
    "NodeBase",
    "NodeCreate",
    "NodeUpdate",
    "NodeRead",
    "EdgeBase",
    "EdgeCreate",
    "EdgeUpdate",
    "EdgeRead",
    "GraphExportResponse",
    "GraphImportPayload",
    "GraphImportResult",
    "NODE_TYPES",
    "NODE_STATUSES",
    "EDGE_TYPES",
]
