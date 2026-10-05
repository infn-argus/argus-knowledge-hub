"""A facility's electronic logbook (Olog), sent here by its daily upload job.

A robot token of the facility's workspace with the *Daily logbook upload* preset (read, create and modify
documents) is what the job uses. See `app/services/olog_logbook.py` and `tools/olog-to-argus`.
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.services import olog_logbook

router = APIRouter(prefix="/v1/logbook/olog", tags=["logbook"])

MAX_BATCH = 500


class OlogBatch(BaseModel):
    # Names the logbook, so two Olog services feeding one workspace never collide (e.g. "btf").
    facility: str = Field(min_length=1, max_length=60)
    # Where a person opens an entry, with {id} for the entry's id (the facility's Olog web client).
    entry_url: Optional[str] = None
    link_equipment: bool = True
    # The entries as Olog's REST API returns them (GET /Olog/logs/search).
    entries: list[dict] = Field(max_length=MAX_BATCH)


@router.post("/entries")
def receive_entries(
    batch: OlogBatch,
    workspace_id: str = Depends(require_permission("create", resource="documents")),
    _modify: str = Depends(require_permission("modify", resource="documents")),
    db: Session = Depends(get_db),
):
    """Store a batch of entries: new ones are created, edited ones get a new revision, the rest are left as
    they are. The answer lists, per entry, the files still to send."""
    return olog_logbook.upsert_entries(db, workspace_id, batch.facility, batch.entries, batch.entry_url,
                                       batch.link_equipment)


@router.post("/entries/{facility}/{entry_id}/attachments", status_code=201)
async def receive_attachment(
    facility: str,
    entry_id: str,
    file: UploadFile = File(...),
    attachment_id: str = Form(...),
    source_url: Optional[str] = Form(default=None),
    workspace_id: str = Depends(require_permission("modify", resource="documents")),
    db: Session = Depends(get_db),
):
    """One of an entry's files. Sending it again changes nothing."""
    content = await file.read()
    try:
        return olog_logbook.add_attachment(db, workspace_id, facility, entry_id, attachment_id,
                                           file.filename or attachment_id, content, file.content_type, source_url)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))
