import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.asset import Asset
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentOut

router = APIRouter(prefix="/v1/attachments", tags=["attachments"])

ATTACHMENTS_DIR = os.environ.get("ATTACHMENTS_DIR", "/data/attachments")


def _get_owned_attachment(uid: str, workspace_id: str, db: Session) -> Attachment:
    attachment = db.get(Attachment, uid)
    if attachment is None or attachment.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    return attachment


@router.post("", response_model=AttachmentOut, status_code=201)
async def upload_attachment(
    asset_uid: str,
    file: UploadFile,
    workspace_id: str = Depends(require_permission("create")),
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_uid)
    if asset is None or asset.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    uid = str(uuid.uuid4())
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    storage_path = os.path.join(ATTACHMENTS_DIR, uid)
    contents = await file.read()
    with open(storage_path, "wb") as f:
        f.write(contents)

    attachment = Attachment(
        uid=uid,
        workspace_id=workspace_id,
        asset_uid=asset_uid,
        filename=file.filename or uid,
        mime_type=file.content_type,
        file_size=len(contents),
        storage_path=storage_path,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get("/{uid}")
def download_attachment(
    uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    attachment = _get_owned_attachment(uid, workspace_id, db)
    return FileResponse(
        attachment.storage_path,
        media_type=attachment.mime_type or "application/octet-stream",
        filename=attachment.filename,
    )


@router.get("/{uid}/verify")
def verify_attachment(uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """Whether the stored file still has the checksum recorded when it arrived."""
    from app.models.attachment import file_sha256
    attachment = _get_owned_attachment(uid, workspace_id, db)
    now = file_sha256(attachment.storage_path)
    return {"uid": uid, "recorded": attachment.sha256, "actual": now,
            "ok": now is not None and now == attachment.sha256, "missing": now is None}


@router.delete("/{uid}", status_code=204)
def delete_attachment(
    uid: str, workspace_id: str = Depends(require_permission("delete")), db: Session = Depends(get_db)
):
    attachment = _get_owned_attachment(uid, workspace_id, db)
    if os.path.exists(attachment.storage_path):
        os.remove(attachment.storage_path)
    db.delete(attachment)
    db.commit()


@router.get("", response_model=list[AttachmentOut])
def list_attachments(
    asset_uid: str | None = None,
    workspace_id: str = Depends(require_permission("read")),
    db: Session = Depends(get_db),
):
    stmt = select(Attachment).where(Attachment.workspace_id == workspace_id)
    if asset_uid:
        stmt = stmt.where(Attachment.asset_uid == asset_uid)
    return db.scalars(stmt).all()
