import os
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.models.icon import Icon
from app.models.workspace import Workspace
from app.schemas.icon import IconOut, IconUpdate

router = APIRouter(prefix="/v1/icons", tags=["icons"])

ATTACHMENTS_DIR = os.environ.get("ATTACHMENTS_DIR", "/data/attachments")


def _get_owned_icon(uid: str, workspace_id: str, db: Session) -> Icon:
    icon = db.get(Icon, uid)
    if icon is None or icon.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Icon not found")
    return icon


def _get_visible_icon(uid: str, workspace_id: str, db: Session) -> Icon:
    icon = db.get(Icon, uid)
    if icon is None or (icon.workspace_id != workspace_id and not icon.is_global):
        raise HTTPException(status_code=404, detail="Icon not found")
    return icon


@router.get("", response_model=list[IconOut])
def list_icons(
    workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    return db.scalars(
        select(Icon).where(or_(Icon.workspace_id == workspace_id, Icon.is_global.is_(True)))
    ).all()


@router.post("", response_model=IconOut, status_code=201)
async def upload_icon(
    file: UploadFile,
    name: str = Form(""),
    workspace_id: str = Depends(require_permission("create")),
    db: Session = Depends(get_db),
):
    uid = str(uuid.uuid4())
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    storage_path = os.path.join(ATTACHMENTS_DIR, uid)
    contents = await file.read()
    with open(storage_path, "wb") as f:
        f.write(contents)

    # A globally-shared workspace shares every icon uploaded to it too,
    # including after the flag was set — the same rule schemas already
    # follow, so an icon from a global workspace doesn't quietly get
    # dropped the next time one of its types is copied elsewhere.
    workspace = db.get(Workspace, workspace_id)
    icon = Icon(
        uid=uid,
        workspace_id=workspace_id,
        name=name.strip() or (file.filename or uid),
        filename=file.filename or uid,
        mime_type=file.content_type,
        file_size=len(contents),
        storage_path=storage_path,
        is_global=bool(workspace is not None and workspace.is_global),
    )
    db.add(icon)
    db.commit()
    db.refresh(icon)
    return icon


@router.get("/{uid}")
def download_icon(
    uid: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)
):
    icon = _get_visible_icon(uid, workspace_id, db)
    return FileResponse(
        icon.storage_path, media_type=icon.mime_type or "application/octet-stream", filename=icon.filename
    )


@router.put("/{uid}", response_model=IconOut)
def update_icon(
    uid: str,
    body: IconUpdate,
    workspace_id: str = Depends(require_permission("modify")),
    db: Session = Depends(get_db),
):
    icon = _get_owned_icon(uid, workspace_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(icon, field, value)
    db.commit()
    db.refresh(icon)
    return icon


@router.delete("/{uid}", status_code=204)
def delete_icon(
    uid: str, workspace_id: str = Depends(require_permission("delete")), db: Session = Depends(get_db)
):
    icon = _get_owned_icon(uid, workspace_id, db)
    db.delete(icon)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not delete this icon — it is still used by one or more types",
        )
    if os.path.exists(icon.storage_path):
        os.remove(icon.storage_path)
