"""Asking a model what type a document is, and keeping the answer as a
proposal.

Two things shape this. The models INFN runs include reasoning ones, which
answer with their working in a `<think>` block before anything useful —
so the reply is parsed defensively rather than assumed to be JSON. And
nothing here writes to a document: it produces rows a person accepts or
rejects, because a library typed by a machine that nobody checked is not
a typed library.
"""
import json
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_suggestion import AISuggestion
from app.models.document import Document, DocumentRevision
from app.models.llm_config import LLMConfig
from app.models.schema import Schema
from app.services.document_types import DEFAULT_DOCUMENT_TYPES, existing_document_type_uids
from app.services.llm import Endpoint, LLMError, complete

# Small enough that one wrong answer doesn't spoil a long batch, large
# enough that 273 documents isn't 273 requests.
BATCH_SIZE = 10

# How much of a document the model is shown. The first paragraphs say what
# a page is; the rest is detail that costs tokens without changing the
# answer.
EXCERPT_CHARS = 900

THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S | re.I)
CODE_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)

SYSTEM_PROMPT = (
    "You classify technical documents from a particle accelerator laboratory into "
    "exactly one type from the list you are given.\n"
    "Answer with JSON only: a list of objects {\"id\": \"<the id>\", \"type\": \"<exact type "
    "name>\"}. No prose, no explanation, no markdown fences.\n"
    "Use a type name exactly as written in the list. If a document is an index, a "
    "placeholder or a landing page with no content of its own, classify it as Note."
)


def parse_classifications(reply: str, valid_types: set[str]) -> dict[str, str]:
    """The id -> type map inside whatever the model actually said.

    Reasoning models put their working in a `<think>` block first, chat
    models like to wrap JSON in a code fence, and both sometimes add a
    sentence afterwards. None of that is an error worth failing a batch
    over — but a type that isn't on the list is, so those are dropped
    rather than invented into the data.
    """
    text = THINK_BLOCK.sub("", reply or "").strip()

    fenced = CODE_FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    # The first JSON array in what's left.
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        rows = json.loads(text[start : end + 1])
    except ValueError:
        return {}

    out: dict[str, str] = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        key, value = row.get("id"), row.get("type")
        if isinstance(key, str) and isinstance(value, str) and value.strip() in valid_types:
            out[key.strip()] = value.strip()
    return out


def _excerpt(db: Session, document: Document) -> str:
    if not document.current_revision_uid:
        return ""
    revision = db.get(DocumentRevision, document.current_revision_uid)
    body = (revision.body_markdown or "") if revision else ""
    return " ".join(body[:EXCERPT_CHARS].split())


def candidate_documents(
    db: Session, workspace_id: str, config: LLMConfig, only_untyped: bool, limit: int
) -> list[Document]:
    """Which documents to ask about.

    Confidential ones are left out unless the endpoint has been marked as
    somewhere they may go — that decision belongs to whoever configured it,
    not to this function.
    """
    stmt = select(Document).where(Document.workspace_id == workspace_id)
    if not config.allow_confidential:
        stmt = stmt.where(Document.confidentiality != "riservato")

    # A proposal does not change the document, so without this the same
    # documents would be asked about on every run and a caller working
    # through the backlog would never reach the end of it.
    pending = set(db.scalars(
        select(AISuggestion.target_uid).where(
            AISuggestion.workspace_id == workspace_id,
            AISuggestion.field == "document_type_uid",
            AISuggestion.status == "proposed",
        )
    ))
    documents = [d for d in db.scalars(stmt) if d.uid not in pending]
    if only_untyped:
        # "Untyped" in practice means the fallback an import chose when it
        # had nothing to go on, not only a null.
        note_uid = f"{workspace_id}:argus-document:note"
        documents = [
            d for d in documents
            if d.document_type_uid in (None, note_uid, f"{workspace_id}:argus-document")
        ]
    return documents[:limit]


def suggest_document_types(
    db: Session,
    workspace_id: str,
    endpoint: Endpoint,
    config: LLMConfig,
    only_untyped: bool = True,
    limit: int = 25,
) -> dict:
    """Propose a type for each candidate document. Writes proposals only."""
    documents = candidate_documents(db, workspace_id, config, only_untyped, limit)
    if not documents:
        return {"considered": 0, "proposed": 0, "unchanged": 0, "failed_batches": 0}

    known_uids = set(existing_document_type_uids(db, workspace_id))
    by_name: dict[str, str] = {}
    for schema in db.scalars(
        select(Schema).where(Schema.workspace_id == workspace_id, Schema.uid.in_(known_uids))
    ):
        by_name[schema.name] = schema.uid
    valid_types = set(by_name)
    if not valid_types:
        return {"considered": 0, "proposed": 0, "unchanged": 0, "failed_batches": 0}

    catalogue = "\n".join(
        f"- {name}: {description}"
        for name, description in DEFAULT_DOCUMENT_TYPES
        if name in valid_types
    )

    proposed = unchanged = failed = 0
    for start in range(0, len(documents), BATCH_SIZE):
        batch = documents[start : start + BATCH_SIZE]
        items = [
            {"id": d.uid, "title": d.title, "excerpt": _excerpt(db, d)} for d in batch
        ]
        user = (
            f"Types:\n{catalogue}\n\n"
            f"Documents:\n{json.dumps(items, ensure_ascii=False)}"
        )
        try:
            # Generous: a reasoning model spends most of its budget thinking
            # before it writes the answer, and a truncated reply is a lost
            # batch.
            reply = complete(endpoint, SYSTEM_PROMPT, user, max_tokens=4000)
        except LLMError:
            failed += 1
            continue

        answers = parse_classifications(reply, valid_types)
        if not answers:
            failed += 1
            continue

        for document in batch:
            name = answers.get(document.uid)
            if not name:
                continue
            type_uid = by_name[name]
            if type_uid == document.document_type_uid:
                unchanged += 1
                continue

            existing = db.scalar(
                select(AISuggestion).where(
                    AISuggestion.target_uid == document.uid,
                    AISuggestion.field == "document_type_uid",
                    AISuggestion.status == "proposed",
                )
            )
            if existing is not None:
                existing.suggested_value = type_uid
                existing.suggested_label = name
                existing.model = endpoint.model
                existing.created_at = datetime.now(timezone.utc)
            else:
                db.add(AISuggestion(
                    workspace_id=workspace_id,
                    target_type="document",
                    target_uid=document.uid,
                    field="document_type_uid",
                    suggested_value=type_uid,
                    suggested_label=name,
                    previous_value=document.document_type_uid,
                    model=endpoint.model,
                ))
            proposed += 1
        db.commit()

    return {
        "considered": len(documents),
        "proposed": proposed,
        "unchanged": unchanged,
        "failed_batches": failed,
    }
