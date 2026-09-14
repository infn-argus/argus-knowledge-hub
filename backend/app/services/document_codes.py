"""Giving a new document its code.

A document's code is its short handle — what people write in a ticket or
say out loud — and it has to be unique across the installation. Asking
whoever is writing the document to invent one that nobody has used is
asking them to do the database's job, and it is the first field on the
form, so it stops them before they have started.

So the system assigns one: a prefix from the document's type, and the
next free number. Anyone who has a real controlled-document number still
types it, and that wins — the point is that leaving it blank works.
"""
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.schema import Schema

FALLBACK_PREFIX = "DOC"


def prefix_for(type_name: Optional[str]) -> str:
    """A short, recognisable prefix for a type name.

    Multi-word names become initials (Work Instruction -> WI) and single
    words their first four letters (Procedure -> PROC), because that is
    how people already abbreviate them on paper.
    """
    words = re.findall(r"[A-Za-z]+", type_name or "")
    if not words:
        return FALLBACK_PREFIX
    if len(words) == 1:
        return words[0][:4].upper()
    return "".join(word[0] for word in words).upper()


def next_code(db: Session, workspace_id: str, document_type_uid: Optional[str]) -> str:
    """The next free code for this type in this workspace.

    Uniqueness is checked against every workspace, since the column is
    unique across the installation — two workspaces both numbering their
    procedures from one would collide on the second.
    """
    schema = db.get(Schema, document_type_uid) if document_type_uid else None
    prefix = prefix_for(schema.name if schema else None)

    used: set[int] = set()
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for (code,) in db.execute(select(Document.code).where(Document.code.like(f"{prefix}-%"))):
        match = pattern.match(code or "")
        if match:
            used.add(int(match.group(1)))

    number = 1
    while number in used:
        number += 1
    return f"{prefix}-{number:04d}"
