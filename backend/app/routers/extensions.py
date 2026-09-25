"""Model extensions (asset-model-revision §5.1, §13 S8): the triggers, the
extensions declared for them, the gate, admission into a catalogue and the
extension's query."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import extensions
from app.auth import get_identity, require_permission
from app.db import get_db
from app.routers.catalogue import _catalogue
from app.routers.ledger import actor_of

router = APIRouter(prefix="/v1/catalogue/extensions", tags=["catalogue"])


@router.get("")
def list_extensions(run_fixtures: bool = False, workspace_id: str = Depends(require_permission("read")),
                    db: Session = Depends(get_db)):
    """Each trigger with the extension declared for it: owner, source, query,
    what the gate says and whether it is admitted here. `run_fixtures` also
    runs each query on its fixture (nothing of it stays)."""
    return {"triggers": extensions.overview(db, workspace_id, run_queries=run_fixtures)}


class AdmitIn(BaseModel):
    reason: str


@router.post("/{ext_id}/admit", status_code=201)
def admit(ext_id: str, body: AdmitIn, identity=Depends(get_identity),
          workspace_id: str = Depends(require_permission("approve")), db: Session = Depends(get_db)):
    _catalogue(db, workspace_id)
    try:
        out = extensions.admit(db, workspace_id, actor_of(identity), ext_id, body.reason)
    except extensions.ExtensionError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail={"error": str(exc)})
    db.commit()
    return out


@router.get("/{ext_id}/query")
def run_query(ext_id: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    """The extension's question, asked of this workspace."""
    try:
        return extensions.run_query(db, workspace_id, ext_id)
    except extensions.ExtensionError as exc:
        raise HTTPException(status_code=422, detail={"error": str(exc)})
