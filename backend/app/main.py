import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import engine
from app.routers import (
    asset_subresources,
    assets,
    attachments,
    documents,
    global_values,
    groups,
    import_configs,
    imports,
    issues,
    labels,
    roles,
    schemas,
    sync,
    workspaces,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ARGUS Asset Knowledge Hub API", version="1.0.0")

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
app.include_router(groups.router)
app.include_router(import_configs.router)
app.include_router(imports.router)
app.include_router(labels.router)
app.include_router(roles.router)
app.include_router(sync.router)
app.include_router(workspaces.router)


@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
