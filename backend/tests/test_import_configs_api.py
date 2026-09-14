"""Saving an import configuration, through the endpoint.

These tests exist because the last round of changes made a token optional
everywhere except the one place that actually refused it — a guard in the
create endpoint, below the schema that had been relaxed and above the
service that no longer needed it. The service-level tests all passed and
the form still failed.
"""
import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_token
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.api_token import ApiToken
from app.models.import_config import ImportConfig
from app.models.workspace import Workspace

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def token():
    ws = f"imp-{secrets.token_hex(4)}"
    raw = secrets.token_urlsafe(16)
    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.flush()
    db.add(ApiToken(workspace_id=ws, token_hash=hash_token(raw)))
    db.commit()
    db.close()
    return ws, raw


def create(raw, config, name="cfg"):
    return client.post(
        "/v1/import-configs",
        json={"name": name, "merge_strategy": "override", "config": config},
        headers={"Authorization": f"Bearer {raw}"},
    )


EPIK8S = {
    "source": "epik8s",
    "provider": "gitlab",
    "repo_url": "https://baltig.infn.it/lnf-da-control/epik8-sparc.git",
    "branch": "main",
    "path": "deploy/values.yaml",
}


def test_a_public_repository_needs_no_token(token):
    """The beamline configurations are readable without one, and requiring
    it means inventing a token to get past a form."""
    ws, raw = token
    resp = create(raw, EPIK8S)
    assert resp.status_code == 201, resp.text

    db = SessionLocal()
    saved = db.get(ImportConfig, resp.json()["uid"])
    assert saved.encrypted_secret is None, "nothing to store, so nothing stored"
    assert saved.params["repo_url"] == EPIK8S["repo_url"]
    db.close()


def test_a_plain_git_import_needs_no_token_either(token):
    _ws, raw = token
    resp = create(raw, {
        "source": "git", "provider": "github",
        "repo_url": "https://github.com/infn-epics/ioc-chart", "branch": "main",
    })
    assert resp.status_code == 201, resp.text


def test_a_token_is_still_stored_when_given(token):
    _ws, raw = token
    resp = create(raw, {**EPIK8S, "pat": "glpat-secret"}, name="with-token")
    assert resp.status_code == 201

    db = SessionLocal()
    saved = db.get(ImportConfig, resp.json()["uid"])
    assert saved.encrypted_secret, "a token given should be kept"
    assert "glpat-secret" not in saved.encrypted_secret, "and encrypted at rest"
    db.close()


def test_jira_still_requires_one_and_says_which_import_it_means(token):
    """Jira has nothing to read without a credential, so an absent one is a
    mistake worth refusing rather than a public-repository case."""
    _ws, raw = token
    resp = create(raw, {
        "source": "jira", "base_url": "https://jira.example.org", "jira_schema_id": "44",
    })
    assert resp.status_code == 422
    assert "jira" in resp.json()["detail"].lower()


def test_confluence_still_requires_one(token):
    _ws, raw = token
    resp = create(raw, {
        "source": "confluence", "base_url": "https://wiki.example.org", "space_key": "LDCG",
    })
    assert resp.status_code == 422


def test_the_saved_configuration_never_returns_the_token(token):
    _ws, raw = token
    resp = create(raw, {**EPIK8S, "pat": "glpat-secret"}, name="secret-check")
    assert "glpat-secret" not in resp.text
    assert "encrypted_secret" not in resp.json()
