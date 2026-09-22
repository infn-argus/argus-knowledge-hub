"""The hub's knowledge, as tools an assistant can call.

ARGUS can already search document text through RAGFlow and read logs
through Loki. What it cannot do is the question the project exists to
answer — "what broke this magnet before, and which procedure covers it" —
because that is a traversal and two structured lookups, and the answer is
in no single document.

These are read-only on purpose. An assistant that can change the
inventory is a different proposal needing a different conversation about
who is accountable for the change; retrieval is where the value is and
where the risk is not.
"""
import json
from typing import Any, Callable, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.asset import Asset, Relation
from app.models.document import Document, DocumentRevision
from app.models.issue import Issue
from app.models.llm_config import LLMConfig
from app.models.schema import Schema
from app.services import causal_model
from app.services.knowledge_graph import graph_summary, traverse
from app.services.alarm_symptoms import root_cause_from_alarms as _root_cause_from_alarms
from app.services.root_cause import blast_radius as _blast_radius
from app.services.root_cause import impact_of as _impact_of
from app.services.root_cause import root_causes as _root_causes

# Enough to answer with, small enough not to bury the model.
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
DOCUMENT_CHARS = 6000


def _confidential_allowed(db: Session, workspace_id: str) -> bool:
    """Whether documents marked riservato may be returned here.

    The same switch that governs sending text to a model, because that is
    exactly what this does — the caller on the other end of an MCP tool is
    an assistant, not a person reading one page.
    """
    config = db.get(LLMConfig, workspace_id)
    return bool(config and config.allow_confidential)


def _asset_visible(db: Session, asset: Asset, workspace_id: str) -> bool:
    """The same rule as the REST API and the graph: this workspace's own
    objects, plus whatever is shared with it.

    An installation that keeps device models in a global workspace needs
    them here too, or "what model is this camera" is unanswerable in the
    tool built to answer it.
    """
    if asset.workspace_id == workspace_id or asset.is_global:
        return True
    schema = db.get(Schema, asset.schema_uid)
    return bool(schema is not None and schema.is_global)


def _document_visible(workspace_id: str):
    """This workspace's documentation, plus whatever is shared with it.

    A global workspace holding the procedures that cover every beamline is
    only worth having if the tools can read them from the beamline asking
    the question.
    """
    return or_(
        Document.workspace_id == workspace_id,
        and_(Document.is_global.is_(True), Document.confidentiality != "riservato"),
    )


def _asset_summary(asset: Asset) -> dict:
    return {
        "uid": asset.uid,
        "key": asset.key,
        "name": asset.name,
        "type": asset.type,
    }


def _issue_summary(issue: Issue) -> dict:
    attributes = issue.attributes or {}
    return {
        "uid": issue.uid,
        "title": issue.title,
        "state": issue.state,
        "source_key": attributes.get("argus_source_key"),
        "category": attributes.get("argus_category"),
        "impact": attributes.get("argus_impact"),
    }


def _document_summary(document: Document, type_name: Optional[str]) -> dict:
    return {
        "uid": document.uid,
        "code": document.code,
        "title": document.title,
        "type": type_name,
    }


# --- the tools ----------------------------------------------------------

def search_objects(db: Session, workspace_id: str, query: str = "",
                   type: Optional[str] = None, limit: int = DEFAULT_LIMIT) -> dict:
    """Equipment by name, key or type."""
    needle = (query or "").strip().lower()
    stmt = select(Asset).where(
        or_(
            Asset.workspace_id == workspace_id,
            Asset.is_global.is_(True),
            Asset.schema_uid.in_(
                select(Schema.uid).where(Schema.is_global.is_(True))
            ),
        )
    )
    if type:
        stmt = stmt.where(Asset.type == type)
    # The type counts as a match. Equipment here is named FI4-B-CAM-VIS-001,
    # so searching "camera" finds nothing by name — and an assistant asked
    # about cameras concludes there are none.
    rows = [
        a for a in db.scalars(stmt)
        if not needle
        or needle in (a.name or "").lower()
        or needle in (a.key or "").lower()
        or needle in (a.type or "").lower()
    ]
    return {
        "total": len(rows),
        "objects": [_asset_summary(a) for a in rows[: min(limit, MAX_LIMIT)]],
    }


def get_object(db: Session, workspace_id: str, uid_or_key: str) -> dict:
    """One object: its attributes, and what it is physically connected to."""
    asset = db.scalar(select(Asset).where(Asset.uid == uid_or_key)) or db.scalar(
        select(Asset).where(Asset.key == uid_or_key)
    )
    if asset is None or not _asset_visible(db, asset, workspace_id):
        return {"found": False, "looked_for": uid_or_key}

    relations = []
    for relation in db.scalars(
        select(Relation).where(
            (Relation.from_asset_uid == asset.uid) | (Relation.to_asset_uid == asset.uid)
        )
    ):
        outgoing = relation.from_asset_uid == asset.uid
        other_uid = relation.to_asset_uid if outgoing else relation.from_asset_uid
        other = db.get(Asset, other_uid)
        relations.append({
            "relation": relation.relation_type,
            "direction": "to" if outgoing else "from",
            "object": _asset_summary(other) if other else {"uid": other_uid},
        })

    return {
        "found": True,
        **_asset_summary(asset),
        "attributes": asset.attributes or {},
        "relations": relations,
    }


def search_tickets(db: Session, workspace_id: str, query: str = "",
                   state: Optional[str] = None, limit: int = DEFAULT_LIMIT) -> dict:
    """Work: faults, maintenance, requests."""
    needle = (query or "").strip().lower()
    stmt = select(Issue).where(Issue.workspace_id == workspace_id)
    if state:
        stmt = stmt.where(Issue.state == state)
    rows = [
        i for i in db.scalars(stmt)
        if not needle
        or needle in (i.title or "").lower()
        or needle in (i.description or "").lower()
    ]
    return {
        "total": len(rows),
        "tickets": [_issue_summary(i) for i in rows[: min(limit, MAX_LIMIT)]],
    }


def get_ticket(db: Session, workspace_id: str, uid: str) -> dict:
    """One ticket, including the ARGUS fields: cause, cure, downtime."""
    issue = db.scalar(
        select(Issue).where(Issue.workspace_id == workspace_id, Issue.uid == uid)
    )
    if issue is None:
        return {"found": False, "looked_for": uid}
    attributes = issue.attributes or {}
    return {
        "found": True,
        **_issue_summary(issue),
        "description": issue.description,
        "labels": issue.labels or [],
        "root_cause": attributes.get("argus_root_cause"),
        "corrective_action": attributes.get("argus_corrective_action"),
        "system": attributes.get("argus_system"),
        "subsystem": attributes.get("argus_subsystem"),
        "downtime_minutes": attributes.get("argus_downtime_minutes"),
    }


def search_documents(db: Session, workspace_id: str, query: str = "",
                     type: Optional[str] = None, limit: int = DEFAULT_LIMIT) -> dict:
    """Documentation by title, code or type."""
    needle = (query or "").strip().lower()
    names = {s.uid: s.name for s in db.scalars(
        select(Schema).where(Schema.workspace_id == workspace_id)
    )}
    stmt = select(Document).where(_document_visible(workspace_id))
    if not _confidential_allowed(db, workspace_id):
        stmt = stmt.where(Document.confidentiality != "riservato")

    rows = []
    for document in db.scalars(stmt):
        type_name = names.get(document.document_type_uid or "")
        if type and (type_name or "").lower() != type.lower():
            continue
        if not needle:
            rows.append(_document_summary(document, type_name))
            continue
        if needle in (document.title or "").lower() or needle in (document.code or "").lower():
            rows.append({**_document_summary(document, type_name), "matched": "title"})
            continue
        # The body too. A documentation search that only reads titles
        # answers "nothing about vacuum" for a library full of it.
        revision = (
            db.get(DocumentRevision, document.current_revision_uid)
            if document.current_revision_uid else None
        )
        body = (revision.body_markdown or "").lower() if revision else ""
        if needle in body:
            where = body.find(needle)
            excerpt = (revision.body_markdown or "")[max(0, where - 80): where + 160]
            rows.append({
                **_document_summary(document, type_name),
                "matched": "text",
                "excerpt": " ".join(excerpt.split()),
            })
    # Title matches first: they are what somebody meant.
    rows.sort(key=lambda r: r.get("matched") != "title")
    return {"total": len(rows), "documents": rows[: min(limit, MAX_LIMIT)]}


def get_document(db: Session, workspace_id: str, uid_or_code: str) -> dict:
    """A document's current text, as Markdown."""
    document = db.scalar(
        select(Document).where(_document_visible(workspace_id), Document.uid == uid_or_code)
    ) or db.scalar(
        select(Document).where(_document_visible(workspace_id), Document.code == uid_or_code)
    )
    if document is None:
        return {"found": False, "looked_for": uid_or_code}
    if document.confidentiality == "riservato" and not _confidential_allowed(db, workspace_id):
        return {
            "found": False,
            "reason": "This document is confidential and this workspace does not allow "
                      "confidential text to be sent to an assistant.",
        }

    revision = (
        db.get(DocumentRevision, document.current_revision_uid)
        if document.current_revision_uid else None
    )
    body = (revision.body_markdown or "") if revision else ""
    names = {s.uid: s.name for s in db.scalars(
        select(Schema).where(Schema.workspace_id == workspace_id)
    )}
    return {
        "found": True,
        **_document_summary(document, names.get(document.document_type_uid or "")),
        "state": revision.state if revision else None,
        "body_markdown": body[:DOCUMENT_CHARS],
        "truncated": len(body) > DOCUMENT_CHARS,
    }


def graph_neighbours(db: Session, workspace_id: str, kind: str, uid: str,
                     depth: int = 1, kinds: Optional[str] = None,
                     max_nodes: int = 60) -> dict:
    """Everything within a few hops: the question RAG cannot answer."""
    graph = traverse(
        db, workspace_id, kind, uid, depth=max(1, min(depth, 4)),
        kinds=[k.strip() for k in kinds.split(",")] if kinds else None,
        max_nodes=max(1, min(max_nodes, 200)),
    )
    return {
        "nodes": [
            {"kind": n.kind, "uid": n.uid, "label": n.label, "sublabel": n.sublabel,
             "type": n.type_name, "state": n.state, "depth": n.depth}
            for n in graph.nodes
        ],
        "edges": [
            {"from": f"{e.from_kind}:{e.from_uid}", "to": f"{e.to_kind}:{e.to_uid}",
             "relation": e.relation, "via": e.via}
            for e in graph.edges
        ],
        "truncated": graph.truncated,
    }


def _line(path: list) -> str:
    """A path as one line an assistant can quote: `A --powers--> B --realized by--> C`."""
    if not path:
        return ""
    return path[0]["provider"] + "".join(f" --{h['relation']}--> {h['dependent']}" for h in path)


def _layer_list(layers: Optional[str]) -> Optional[list]:
    return [x.strip() for x in layers.split(",") if x.strip()] if layers else None


def impact_analysis(db: Session, workspace_id: str, uid_or_key: str, layers: Optional[str] = None,
                    max_depth: int = 6, limit: int = 40) -> dict:
    """This stopped: what does it take with it?"""
    result = _impact_of(db, workspace_id, uid_or_key, layers=_layer_list(layers),
                        max_depth=max(1, min(max_depth, 8)))
    if result is None:
        return {"found": False}
    limit = max(1, min(limit, MAX_LIMIT))
    return {
        "found": True, "origin": result["origin"]["key"], "count": result["count"],
        "by_type": result["by_type"], "by_loss": result["by_loss"],
        "affected": [
            {"key": a["key"], "type": a["type"], "loses": list(a["losses"]), "depth": a["depth"],
             "path": _line(a["path"]), "inferred": a["via_inference"]}
            for a in result["affected"][:limit]
        ],
        "shown": min(limit, result["count"]), "truncated": result["truncated"],
        "unclassified_relations": result["unclassified_relations"],
    }


def root_cause_analysis(db: Session, workspace_id: str, symptoms: str, healthy: Optional[str] = None,
                        layers: Optional[str] = None, control_symptoms: Optional[str] = None,
                        max_depth: int = 6, top: int = 5) -> dict:
    """These are misbehaving: what would explain them?"""
    listed = lambda text: [x.strip() for x in (text or "").split(",") if x.strip()]
    kinds = {s: causal_model.CONTROL for s in listed(control_symptoms)}
    result = _root_causes(
        db, workspace_id, listed(symptoms), healthy=listed(healthy), layers=_layer_list(layers),
        max_depth=max(1, min(max_depth, 8)), top=max(1, min(top, 15)), symptom_kind=kinds)
    return {
        "not_found": result["not_found"],
        "candidates": [
            {"key": c["key"], "type": c["type"], "fit": c["fit"], "parsimony": c["parsimony"],
             "explains": [{"symptom": e["key"], "loses": e["loss"], "path": _line(e["path"]),
                           "inferred": e["via_inference"]} for e in c["explains"]],
             "would_also_affect": c["would_also_affect"], "contradicted_by": c["contradicted_by"],
             "earlier_tickets": c["history"]}
            for c in result["candidates"]
        ],
        "fewest_causes": [
            {"causes": [{"key": x["key"], "explains": x["explains"]} for x in h["causes"]],
             "unexplained": h["unexplained"]}
            for h in result["hypotheses"]
        ],
    }


def root_cause_from_alarms(db: Session, workspace_id: str, alarms: list, layers: Optional[str] = None,
                           max_depth: int = 6, top: int = 5) -> dict:
    """A raw alarm feed in, a root-cause answer out. See `root_cause_analysis` for the fields on
    each candidate; this additionally reports which alarms could not be placed on an object."""
    result = _root_cause_from_alarms(db, workspace_id, alarms, layers=_layer_list(layers),
                                     max_depth=max(1, min(max_depth, 8)), top=max(1, min(top, 15)))
    if not result["candidates"]:
        return {"placed": result["placed"], "unresolved": result["unresolved"], "candidates": [],
                "fewest_causes": []}
    return {
        "placed": result["placed"], "unresolved": result["unresolved"],
        "candidates": [
            {"key": c["key"], "type": c["type"], "fit": c["fit"], "parsimony": c["parsimony"],
             "explains": [{"symptom": e["key"], "loses": e["loss"], "path": _line(e["path"]),
                           "inferred": e["via_inference"]} for e in c["explains"]],
             "would_also_affect": c["would_also_affect"], "contradicted_by": c["contradicted_by"],
             "earlier_tickets": c["history"]}
            for c in result["candidates"]
        ],
        "fewest_causes": [
            {"causes": [{"key": x["key"], "explains": x["explains"]} for x in h["causes"]],
             "unexplained": h["unexplained"]}
            for h in result["hypotheses"]
        ],
    }


def single_points_of_failure(db: Session, workspace_id: str, layers: Optional[str] = None,
                             top: int = 15) -> dict:
    """What would take the most with it."""
    result = _blast_radius(db, workspace_id, layers=_layer_list(layers), top=max(1, min(top, 50)))
    return {"assets": [
        {"key": a["key"], "type": a["type"], "loses_function": a["function"],
         "loses_readout": a["control"], "degrades": a["degradation"]}
        for a in result["assets"]
    ], "considered": result["considered"]}


def knowledge_summary(db: Session, workspace_id: str) -> dict:
    """How much of a graph this workspace actually has."""
    return graph_summary(db, workspace_id)


# --- the catalogue ------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_objects",
        "description": "Search equipment (objects) by name, key or type name. Returns "
                       "uid, key, name and type.",
        "handler": search_objects,
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to look for in the name or key"},
                "type": {"type": "string", "description": "Restrict to one object type"},
                "limit": {"type": "integer", "description": f"Default {DEFAULT_LIMIT}"},
            },
        },
    },
    {
        "name": "get_object",
        "description": "One object by uid or key, with its attributes and the objects it "
                       "is physically connected to.",
        "handler": get_object,
        "inputSchema": {
            "type": "object",
            "properties": {"uid_or_key": {"type": "string"}},
            "required": ["uid_or_key"],
        },
    },
    {
        "name": "search_tickets",
        "description": "Search tickets — faults, maintenance, requests — by text, "
                       "optionally filtered by state.",
        "handler": search_tickets,
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "state": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_ticket",
        "description": "One ticket by uid, including root cause, corrective action, "
                       "affected system and downtime where they are recorded.",
        "handler": get_ticket,
        "inputSchema": {
            "type": "object",
            "properties": {"uid": {"type": "string"}},
            "required": ["uid"],
        },
    },
    {
        "name": "search_documents",
        "description": "Search documentation by title, code, document type "
                       "(Procedure, Runbook, Specification, Logbook Entry, …) or the "
                       "text of the document itself. Text matches come back with the "
                       "surrounding sentence.",
        "handler": search_documents,
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "type": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_document",
        "description": "A document's current text as Markdown, by uid or code.",
        "handler": get_document,
        "inputSchema": {
            "type": "object",
            "properties": {"uid_or_code": {"type": "string"}},
            "required": ["uid_or_code"],
        },
    },
    {
        "name": "graph_neighbours",
        "description": "Everything connected to one record within a few hops, across "
                       "objects, tickets, documents and people. Use this for questions "
                       "like 'what broke this magnet before' or 'which procedure covers "
                       "this camera' — the answer spans records and is in no single "
                       "document. kind is one of asset, ticket, document, group, person.",
        "handler": graph_neighbours,
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "description": "asset | ticket | document | group | person"},
                "uid": {"type": "string"},
                "depth": {"type": "integer", "description": "1 to 4, default 1"},
                "kinds": {"type": "string", "description": "Comma-separated kinds to keep"},
                "max_nodes": {"type": "integer"},
            },
            "required": ["kind", "uid"],
        },
    },
    {
        "name": "impact_analysis",
        "description": "This object stopped: what does it take with it? Follows what depends on what "
                       "(power, cooling, control, timing, interlocks, composition) and says for each "
                       "affected object what it loses — its readout ('control') or its function — and "
                       "by which path. A lost IOC costs the readout of the pump behind it, not the "
                       "pump. Objects are given by key or uid. layers narrows the walk, e.g. "
                       "'power,cooling'.",
        "handler": impact_analysis,
        "inputSchema": {
            "type": "object",
            "properties": {
                "uid_or_key": {"type": "string"},
                "layers": {"type": "string", "description": "Comma-separated: control, power, cooling, "
                           "vacuum, timing, interlock, function, composition, membership, beam, environment"},
                "max_depth": {"type": "integer", "description": "1 to 8, default 6"},
                "limit": {"type": "integer"},
            },
            "required": ["uid_or_key"],
        },
    },
    {
        "name": "root_cause_analysis",
        "description": "These objects misbehave: what would explain them? Give the symptoms by key "
                       "(comma-separated), and if known which objects still work (healthy) and which "
                       "symptoms are only a lost readout (control_symptoms, e.g. a PV that "
                       "disconnected). Returns candidates ranked by how well they fit, each with the "
                       "path to every symptom, what it would also have broken, and earlier tickets "
                       "that named it, plus the fewest causes that explain everything. Paths through "
                       "inferred objects are marked. Rank is evidence to argue with, not a probability.",
        "handler": root_cause_analysis,
        "inputSchema": {
            "type": "object",
            "properties": {
                "symptoms": {"type": "string", "description": "Comma-separated object keys or uids"},
                "healthy": {"type": "string", "description": "Comma-separated objects known to work"},
                "control_symptoms": {"type": "string", "description": "Which symptoms are only a lost readout"},
                "layers": {"type": "string"},
                "max_depth": {"type": "integer"},
                "top": {"type": "integer"},
            },
            "required": ["symptoms"],
        },
    },
    {
        "name": "root_cause_from_alarms",
        "description": "The alarm-feed version of root_cause_analysis: give the PVs currently in "
                       "alarm (and, if known, the ones reporting OK) and this resolves each to an "
                       "object, reads whether it lost its readout or its function from the EPICS "
                       "severity (INVALID -> readout, MINOR/MAJOR -> function; OK is evidence the "
                       "object works), and ranks candidates the same way root_cause_analysis does. "
                       "A lost permit is never guessed from a severity — pass kind: 'permit' on "
                       "that alarm when you know one. Alarms are objects with pv (required), "
                       "severity, status and an optional kind override; what cannot be placed on "
                       "an object is reported under 'unresolved'.",
        "handler": root_cause_from_alarms,
        "inputSchema": {
            "type": "object",
            "properties": {
                "alarms": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pv": {"type": "string"},
                            "severity": {"type": "string", "description": "OK, MINOR, MAJOR or INVALID"},
                            "status": {"type": "string"},
                            "kind": {"type": "string", "description": "control | function | permit"},
                        },
                        "required": ["pv"],
                    },
                },
                "layers": {"type": "string"},
                "max_depth": {"type": "integer"},
                "top": {"type": "integer"},
            },
            "required": ["alarms"],
        },
    },
    {
        "name": "single_points_of_failure",
        "description": "The objects whose failure would take the most with it: how many others lose "
                       "their function, their readout, or are degraded.",
        "handler": single_points_of_failure,
        "inputSchema": {
            "type": "object",
            "properties": {"layers": {"type": "string"}, "top": {"type": "integer"}},
        },
    },
    {
        "name": "knowledge_summary",
        "description": "How many objects, tickets and documents this workspace holds, and "
                       "how many connections of each kind exist between them.",
        "handler": knowledge_summary,
        "inputSchema": {"type": "object", "properties": {}},
    },
]

BY_NAME: dict[str, dict] = {tool["name"]: tool for tool in TOOLS}


def catalogue() -> list[dict]:
    """The tools as MCP describes them — without the Python handlers."""
    return [
        {k: v for k, v in tool.items() if k != "handler"}
        for tool in TOOLS
    ]


def call(db: Session, workspace_id: str, name: str, arguments: dict) -> str:
    """Run one tool and return its result as text, which is what MCP carries."""
    tool = BY_NAME.get(name)
    if tool is None:
        raise KeyError(name)
    handler: Callable = tool["handler"]
    allowed = {
        key: value
        for key, value in (arguments or {}).items()
        if key in tool["inputSchema"].get("properties", {})
    }
    result = handler(db, workspace_id, **allowed)
    return json.dumps(result, ensure_ascii=False, default=str, indent=2)
