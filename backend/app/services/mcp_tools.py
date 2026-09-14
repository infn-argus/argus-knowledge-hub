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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, Relation
from app.models.document import Document, DocumentRevision
from app.models.issue import Issue
from app.models.llm_config import LLMConfig
from app.models.schema import Schema
from app.services.knowledge_graph import graph_summary, traverse

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
    stmt = select(Asset).where(Asset.workspace_id == workspace_id)
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
    asset = db.scalar(
        select(Asset).where(Asset.workspace_id == workspace_id, Asset.uid == uid_or_key)
    ) or db.scalar(
        select(Asset).where(Asset.workspace_id == workspace_id, Asset.key == uid_or_key)
    )
    if asset is None:
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
    stmt = select(Document).where(Document.workspace_id == workspace_id)
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
        select(Document).where(
            Document.workspace_id == workspace_id, Document.uid == uid_or_code
        )
    ) or db.scalar(
        select(Document).where(
            Document.workspace_id == workspace_id, Document.code == uid_or_code
        )
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
