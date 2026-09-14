"""What has already been written in an attribute.

An attribute marked `indexed` is a key, not free prose: "BTF", "Vacuum",
"CS-Studio" are meant to be the same term every time they are used. A
plain text box guarantees they won't be — "BTF", "btf" and "BTF " become
three values that no filter can bring back together — so an indexed
attribute offers what the workspace has already used, and this is where
that list comes from.

Deliberately derived rather than stored: the vocabulary of a workspace is
whatever its records actually say, including everything an import brought
in. A separate table of allowed terms would start empty and drift.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db

router = APIRouter(prefix="/v1/attribute-values", tags=["attributes"])

MAX_VALUES = 500

# Where each kind of record keeps its attributes. Documents are the odd one
# out: the values live on the revision, and only the current revision of
# each document counts — a term dropped three revisions ago is not part of
# the vocabulary any more.
SOURCES = {
    "objects": """
        SELECT a.attributes AS attrs FROM assets a WHERE a.workspace_id = :ws
    """,
    "tickets": """
        SELECT i.attributes AS attrs FROM issues i WHERE i.workspace_id = :ws
    """,
    "documents": """
        SELECT r.attributes AS attrs
          FROM documents d
          JOIN document_revisions r ON r.uid = d.current_revision_uid
         WHERE d.workspace_id = :ws
    """,
}


@router.get("", response_model=list[str])
def list_attribute_values(
    applies_to: Literal["objects", "tickets", "documents"] = Query(
        description="Which kind of record to read the values from"
    ),
    key: str = Query(description="The attribute key, e.g. argus_components"),
    q: Optional[str] = Query(None, description="Only values containing this text"),
    limit: int = Query(50, ge=1, le=MAX_VALUES),
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    """Every distinct value this attribute holds in this workspace.

    A value can be stored as a string or, for a multi-value attribute, as an
    array of them; both are read, because one attribute's definition can
    change from single to multi and the older records keep their shape.
    """
    source = SOURCES[applies_to]
    # A set-returning function can't sit inside CASE, so the two shapes are
    # unioned rather than branched.
    sql = text(f"""
        WITH records AS ({source})
        SELECT DISTINCT value FROM (
            SELECT attrs ->> :key AS value
              FROM records
             WHERE jsonb_typeof(attrs -> :key) = 'string'
            UNION
            SELECT element AS value
              FROM records,
                   LATERAL jsonb_array_elements_text(attrs -> :key) AS element
             WHERE jsonb_typeof(attrs -> :key) = 'array'
        ) AS values
        WHERE value IS NOT NULL
          AND btrim(value) <> ''
          AND (:q IS NULL OR value ILIKE :pattern)
        ORDER BY value
        LIMIT :limit
    """)
    rows = db.execute(
        sql,
        {
            "ws": workspace_id,
            "key": key,
            "q": q,
            "pattern": f"%{q}%" if q else None,
            "limit": limit,
        },
    )
    return [row[0] for row in rows]
