from typing import Optional

from pydantic import BaseModel


class GraphNodeOut(BaseModel):
    kind: str
    uid: str
    label: str
    sublabel: Optional[str] = None
    type_name: Optional[str] = None
    state: Optional[str] = None
    depth: int
    restricted: bool = False


class GraphEdgeOut(BaseModel):
    from_kind: str
    from_uid: str
    to_kind: str
    to_uid: str
    relation: str
    via: str


class GraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    # True when the node cap stopped the walk — the graph is a subset, and
    # saying so is better than a silently partial answer.
    truncated: bool


class GraphSummaryOut(BaseModel):
    nodes: dict[str, int]
    edges: dict[str, int]
