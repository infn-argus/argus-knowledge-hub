import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import engine
from app.routers import (
    access_reviews,
    ai,
    asset_subresources,
    assets,
    attachments,
    attribute_values,
    documents,
    equipment,
    export,
    global_values,
    graph,
    groups,
    hub,
    ledger,
    icons,
    import_configs,
    imports,
    issues,
    labels,
    mcp,
    roles,
    schemas,
    sync,
    transfers,
    workflows,
    workspaces,
)

logging.basicConfig(level=logging.INFO)

from app.auth import bind_grants  # noqa: E402
import app.ledger.audit  # noqa: E402,F401  (append-only guards on create_all)

# Every request carries the viewer's restricted-class grants (I-ACL-1).
app = FastAPI(title="ARGUS Asset Knowledge Hub API", version="1.0.0", dependencies=[Depends(bind_grants)])

# Auth is a Bearer token per request (no cookies), so a wildcard origin here
# carries none of the usual CSRF-adjacent risk of credentialed CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schemas.router)
app.include_router(assets.router)
app.include_router(assets.relations_router)
app.include_router(issues.router)
app.include_router(documents.router)
app.include_router(asset_subresources.router)
app.include_router(attachments.router)
app.include_router(global_values.router)
app.include_router(graph.router)
app.include_router(hub.router)
app.include_router(ledger.router)
app.include_router(ledger.installations_router)
app.include_router(ledger.access_points_router)
app.include_router(ledger.domains_router)
app.include_router(ledger.lookup_router)
app.include_router(export.router)
app.include_router(equipment.router)
app.include_router(equipment.bulk_router)
app.include_router(workflows.router)
app.include_router(workflows.notifications_router)
app.include_router(access_reviews.router)
app.include_router(attribute_values.router)
app.include_router(ai.router)
app.include_router(mcp.router)
app.include_router(groups.router)
app.include_router(icons.router)
app.include_router(import_configs.router)
app.include_router(imports.router)
app.include_router(labels.router)
app.include_router(roles.router)
app.include_router(sync.router)
app.include_router(transfers.router)
app.include_router(workspaces.router)


@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
