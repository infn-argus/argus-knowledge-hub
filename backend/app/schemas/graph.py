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


class SemanticEdgeOut(BaseModel):
    """Two records whose written knowledge is about the same thing: how close (0 to 1), and the closest
    passages on each side, so the link explains itself."""
    from_kind: str
    from_uid: str
    to_kind: str
    to_uid: str
    relation: str = "similar"
    score: float
    excerpt: str
    matched: str


class SemanticGraphOut(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[SemanticEdgeOut]
    available: bool = True
    reason: Optional[str] = None
    # What the start node was compared by: its indexed "passages", or its "description" when it has none.
    basis: Optional[str] = None
