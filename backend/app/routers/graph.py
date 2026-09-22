from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.schemas.graph import GraphOut, GraphSummaryOut
from app.services import causal_model
from app.services.knowledge_graph import MAX_NODES, graph_summary, traverse
from app.services.alarm_symptoms import root_cause_from_alarms
from app.services.root_cause import MAX_DEPTH, blast_radius, impact_of, root_causes

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


def _layers(value: Optional[str]) -> Optional[list]:
    layers = [x.strip() for x in value.split(",") if x.strip()] if value else None
    unknown = [x for x in (layers or []) if x not in causal_model.LAYERS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown layer: {', '.join(unknown)}. "
                                                    f"Layers are {', '.join(causal_model.LAYERS)}.")
    return layers


@router.get("/relation-semantics")
def get_relation_semantics(workspace_id: str = Depends(require_permission("read"))):
    """Which way a failure travels along each kind of relation, and what it takes away.

    The rules impact and root-cause analysis run on, so a person or an assistant can read them
    instead of guessing."""
    return {
        "layers": causal_model.LAYERS,
        "relations": {
            name: {"layer": m.layer, "flows": m.flows, "carries": m.carries, "weak": m.weak, "note": m.note}
            for name, m in causal_model.SEMANTICS.items()
        },
    }


@router.get("/impact")
def get_impact(
    uid: str = Query(description="The object that failed, by uid or key"),
    layers: Optional[str] = Query(None, description="Comma-separated layers to follow, e.g. 'power,cooling'"),
    max_depth: int = Query(6, ge=1, le=MAX_DEPTH),
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    """This stopped: what does it take with it, how, and by which path?"""
    result = impact_of(db, workspace_id, uid, layers=_layers(layers), max_depth=max_depth)
    if result is None:
        raise HTTPException(status_code=404, detail="No such object in this workspace")
    return result


class RootCauseRequest(BaseModel):
    symptoms: list[str] = Field(min_length=1, description="Objects that misbehave, by uid or key")
    healthy: list[str] = Field(default_factory=list, description="Objects known to be working")
    symptom_kind: dict[str, str] = Field(
        default_factory=dict,
        description="symptom -> 'control' (its readout is gone), 'function' (it stopped doing its job) or 'permit' (it will not run because a condition is not met)")
    layers: Optional[list[str]] = None
    max_depth: int = Field(6, ge=1, le=MAX_DEPTH)
    top: int = Field(10, ge=1, le=50)


@router.post("/root-cause")
def post_root_cause(
    body: RootCauseRequest,
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    """These are misbehaving: what would explain them? Candidates ranked by how well they fit,
    with the path to every symptom, and the fewest causes that explain them all."""
    bad = [k for k, v in body.symptom_kind.items()
           if v not in (causal_model.CONTROL, causal_model.FUNCTION, causal_model.PERMIT)]
    if bad:
        raise HTTPException(status_code=422, detail="symptom_kind must be 'control', 'function' or 'permit'")
    return root_causes(
        db, workspace_id, body.symptoms, healthy=body.healthy, layers=_layers(",".join(body.layers or [])),
        max_depth=body.max_depth, top=body.top, symptom_kind=body.symptom_kind,
    )


@router.get("/blast-radius")
def get_blast_radius(
    layers: Optional[str] = Query(None),
    top: int = Query(20, ge=1, le=100),
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    """The single points of failure: what would take the most with it."""
    return blast_radius(db, workspace_id, layers=_layers(layers), top=top)


class AlarmIn(BaseModel):
    pv: str
    severity: str = Field("", description="OK, MINOR, MAJOR or INVALID (EPICS convention)")
    status: str = Field("", description="The alarm's own message, e.g. 'Disconnected', 'HIHI'")
    kind: Optional[str] = Field(
        None, description="Override what is lost — 'control', 'function' or 'permit' — instead of "
                          "reading it from severity. Only way to report a lost permit.")


class RootCauseFromAlarmsRequest(BaseModel):
    alarms: list[AlarmIn] = Field(min_length=1)
    layers: Optional[list[str]] = None
    max_depth: int = Field(6, ge=1, le=MAX_DEPTH)
    top: int = Field(10, ge=1, le=50)


@router.post("/root-cause/from-alarms")
def post_root_cause_from_alarms(
    body: RootCauseFromAlarmsRequest,
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    """A raw alarm feed in, a root-cause answer out. Each alarm names a PV; this resolves it
    against `Control Device.pv` and `IOC.pv_prefix`, reads `control` or `function` from its EPICS
    severity (a permit is never guessed — give `kind: "permit"` when you know one is lost), and
    treats an `OK` alarm as evidence the object it names still works. What cannot be placed is
    reported under `unresolved` rather than dropped."""
    return root_cause_from_alarms(
        db, workspace_id, [a.model_dump() for a in body.alarms], layers=_layers(",".join(body.layers or [])),
        max_depth=body.max_depth, top=body.top,
    )
