"""Complete export in open formats (asset-model-revision §19 item 9).

JSON lines: one record per line, per kind (see app/ledger/portability.py,
which also loads a bundle into an empty instance). What a viewer may not
see — restricted classes they hold no grant for — is not exported (I-ACL-1).
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import require_permission
from app.db import get_db
from app.ledger import portability

router = APIRouter(prefix="/v1/export", tags=["export"])

KINDS = portability.KINDS


@router.get("/{kind}")
def export(kind: str, workspace_id: str = Depends(require_permission("read")), db: Session = Depends(get_db)):
    if kind not in KINDS:
        raise HTTPException(status_code=404, detail=f"export kinds are {', '.join(KINDS)}")
    # Materialized before the session closes: the response streams after the request.
    body = list(portability.lines(db, workspace_id, kind))
    return StreamingResponse(iter(body), media_type="application/x-ndjson",
                             headers={"Content-Disposition": f'attachment; filename="{workspace_id}-{kind}.jsonl"'})
