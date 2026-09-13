from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.schemas.graph import GraphOut, GraphSummaryOut
from app.services.knowledge_graph import MAX_NODES, graph_summary, traverse

router = APIRouter(prefix="/v1/graph", tags=["graph"])


@router.get("/summary", response_model=GraphSummaryOut)
def get_graph_summary(
    workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    return graph_summary(db, workspace_id)


@router.get("", response_model=GraphOut)
def get_graph(
    kind: str = Query(description="asset | ticket | document | group | person"),
    uid: str = Query(description="The node to start from"),
    depth: int = Query(1, ge=1, le=4),
    kinds: Optional[str] = Query(
        None,
        description="Comma-separated node kinds to keep, e.g. 'asset,document'",
    ),
    max_nodes: int = Query(MAX_NODES, ge=1, le=MAX_NODES),
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    """Everything within `depth` hops of one node, across objects, tickets,
    documents and people.

    Depth is capped at 4 deliberately: in a real inventory a hub object
    reaches most of the graph by the third hop, and an answer that large
    helps nobody.
    """
    graph = traverse(
        db, workspace_id, kind, uid, depth=depth,
        kinds=[k.strip() for k in kinds.split(",")] if kinds else None,
        max_nodes=max_nodes,
    )
    if not graph.nodes:
        raise HTTPException(status_code=404, detail="No such node in this workspace")
    return graph
