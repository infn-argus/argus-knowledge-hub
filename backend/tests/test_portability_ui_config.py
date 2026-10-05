"""Portability set-up from the web app: repositories, trusted keys and the signing key registered by
administrators, added to the deployment's own set-up, never replacing it, with secrets never shown and an
off switch (ARGUS_PORTABILITY_UI_CONFIG)."""
import subprocess
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.auth import OidcIdentity, get_identity
from app.db import SessionLocal
from app.main import app
from app.models.portability import PortabilityEvent
from app.models.portability_config import (PortabilityRepository, PortabilitySigningKey, PortabilityStore,
                                           PortabilityTrustedKey)
from app.models.user import User
from app.portability import service, signing, ui_config

client = TestClient(app)
HOST_KEYS = [{"line": "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl",
              "type": "ssh-ed25519", "fingerprint": "SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU"}]


def _wipe(db):
    for model in (PortabilityRepository, PortabilityTrustedKey, PortabilitySigningKey, PortabilityStore):
        db.execute(delete(model))
    db.commit()


@pytest.fixture()
def setup(tmp_path, monkeypatch):
    root = tmp_path / "portability"
    root.mkdir()
    for name in ("ARGUS_PORTABILITY_REPOSITORIES", "ARGUS_PORTABILITY_SIGNING_KEY", "ARGUS_PORTABILITY_TRUSTED_KEYS",
                 "ARGUS_PORTABILITY_UI_CONFIG", "ARGUS_PORTABILITY_POLICY_SEPARATION_OF_DUTIES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ARGUS_PORTABILITY_ROOT", str(root))
    monkeypatch.setattr(ui_config, "scan_host_keys", lambda host, port: list(HOST_KEYS))
    db = SessionLocal()
    _wipe(db)
    t = uuid.uuid4().hex[:6]
    alice = User(id=f"alice-{t}", email=f"alice-{t}@argus.test", is_admin=True)
    bob = User(id=f"bob-{t}", email=f"bob-{t}@argus.test", is_admin=True)
    db.add_all([alice, bob])
    db.commit()
    for u in (alice, bob):
        db.refresh(u)
        db.expunge(u)
    yield {"db": db, "root": root, "alice": alice, "bob": bob}
    app.dependency_overrides.pop(get_identity, None)
    _wipe(db)
    db.close()


def as_(user):
    app.dependency_overrides[get_identity] = lambda: OidcIdentity(user=user, claims={"auth_time": time.time()})


def test_an_https_repository_with_a_token_is_used_and_its_token_never_shown(setup):
    as_(setup["alice"])
    r = client.post("/v1/portability/setup/repositories", json={
        "name": "escrow-gh", "url": "https://x-access-token@github.com/infn-argus/escrow.git",
        "token": "ghp_secret_value_123", "confirm": True})
    assert r.status_code == 201, r.text
    assert r.json()["auth"] == "https" and r.json()["provider"] == "github" and r.json()["usable"]
    page = client.get("/v1/portability/setup")
    assert "ghp_secret_value_123" not in page.text and page.json()["repositories"][0]["has_token"]
    cfg = service.config()
    assert cfg.repositories["escrow-gh"].startswith("https://") and cfg.sources["repositories"]["escrow-gh"] == "web"
    token_file = cfg.repository_tokens["escrow-gh"]
    assert token_file.read_text() == "ghp_secret_value_123" and oct(token_file.stat().st_mode)[-3:] == "600"
    assert str(setup["root"]) not in str(token_file)            # never written to the shared volume


def test_an_ssh_repository_gets_a_deploy_key_and_is_used_only_once_its_host_keys_are_confirmed(setup):
    as_(setup["alice"])
    r = client.post("/v1/portability/setup/repositories",
                    json={"name": "escrow", "url": "git@github.com:infn-argus/escrow.git", "confirm": True}).json()
    assert r["public_key"].startswith("ssh-ed25519 ") and "PRIVATE" not in str(r)
    assert r["host_keys"][0]["fingerprint"].startswith("SHA256:") and not r["usable"]
    assert "escrow" not in service.config().repositories      # not before the server is confirmed
    wrong = client.post("/v1/portability/setup/repositories/escrow/host-keys/confirm",
                        json={"fingerprints": ["SHA256:something-else"], "confirm": True})
    assert wrong.status_code == 409
    ok = client.post("/v1/portability/setup/repositories/escrow/host-keys/confirm",
                     json={"fingerprints": [HOST_KEYS[0]["fingerprint"]], "confirm": True}).json()
    assert ok["usable"]
    cfg = service.config()
    assert cfg.repositories["escrow"] == "git@github.com:infn-argus/escrow.git"
    assert "BEGIN OPENSSH PRIVATE KEY" in cfg.repository_keys["escrow"].read_text()
    env = cfg.git_env("escrow")
    assert f"UserKnownHostsFile={cfg.repository_known_hosts['escrow']}" in env["GIT_SSH_COMMAND"]
    assert "StrictHostKeyChecking=yes" in env["GIT_SSH_COMMAND"]


def test_addresses_and_names_that_are_refused(setup, monkeypatch):
    as_(setup["alice"])
    post = lambda **b: client.post("/v1/portability/setup/repositories", json={"confirm": True, **b})  # noqa: E731
    assert post(name="x1", url="http://github.com/o/r.git").status_code == 422
    assert post(name="x2", url="https://user:pw@github.com/o/r.git").status_code == 422
    assert post(name="x3", url="/etc/passwd").status_code == 422               # outside the portability area
    assert post(name="Bad Name", url="https://github.com/o/r.git").status_code == 422
    monkeypatch.setenv("ARGUS_PORTABILITY_REPOSITORIES", "escrow=/srv/escrow.git")
    assert post(name="escrow", url="https://github.com/o/r.git").status_code == 409   # the deployment's
    local = setup["root"] / "escrow-local.git"
    assert post(name="escrow-local", url=str(local)).json()["auth"] == "local"


def test_a_repository_on_this_installation_is_tested_for_reading_and_writing(setup):
    as_(setup["alice"])
    bare = setup["root"] / "copied.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    client.post("/v1/portability/setup/repositories", json={"name": "copied", "url": str(bare), "confirm": True})
    tested = client.post("/v1/portability/setup/repositories/copied/test", json={"write": True}).json()
    assert tested["last_test"]["read"] is True and tested["last_test"]["write"] is True, tested["last_test"]
    branches = subprocess.run(["git", "--git-dir", str(bare), "branch", "--list"], capture_output=True, text=True)
    assert "argus-connection-test" not in branches.stdout                   # pushed, then deleted


def test_trusted_keys_and_a_signing_key_made_here_are_used(setup, tmp_path):
    as_(setup["alice"])
    other = signing.new_key(tmp_path / "other_key")
    other.principal = "argus-dev"
    line = signing.allowed_signers_line(other).strip()
    assert client.post("/v1/portability/setup/trusted-keys", json={"line": "nonsense", "confirm": True}).status_code == 422
    added = client.post("/v1/portability/setup/trusted-keys",
                        json={"line": line, "note": "my laptop", "confirm": True}).json()
    assert added["principal"] == "argus-dev" and added["key_id"] == other.key_id
    assert client.post("/v1/portability/setup/trusted-keys",
                       json={"line": line, "confirm": True}).status_code == 409    # once
    made = client.post("/v1/portability/setup/signing-key", json={"principal": "argus-infn", "confirm": True}).json()
    assert made["public_line"].startswith('argus-infn namespaces="git,') and made["status"] == "active"
    cfg = service.config()
    assert cfg.signer is not None and cfg.signer.principal == "argus-infn" and cfg.signer.key_id == made["key_id"]
    trusted = signing.trusted_keys(cfg.trusted)
    assert other.key_id in trusted and made["key_id"] in trusted               # its own archives verify too
    again = client.post("/v1/portability/setup/signing-key", json={"confirm": True}).json()
    db = setup["db"]
    db.expire_all()
    assert db.get(PortabilitySigningKey, made["id"]).status == "retired" and again["status"] == "active"


def test_the_deployments_signing_key_and_trusted_keys_come_first(setup, tmp_path, monkeypatch):
    own = signing.new_key(tmp_path / "deploy_key")
    allowed = tmp_path / "allowed_signers"
    allowed.write_text(signing.allowed_signers_line(own))
    monkeypatch.setenv("ARGUS_PORTABILITY_SIGNING_KEY", str(own.key_path))
    monkeypatch.setenv("ARGUS_PORTABILITY_TRUSTED_KEYS", str(allowed))
    as_(setup["alice"])
    assert client.post("/v1/portability/setup/signing-key", json={"confirm": True}).status_code == 409
    other = signing.new_key(tmp_path / "other")
    client.post("/v1/portability/setup/trusted-keys",
                json={"line": signing.allowed_signers_line(other), "confirm": True})
    cfg = service.config()
    assert cfg.signer.key_path == own.key_path
    assert {own.key_id, other.key_id} <= set(signing.trusted_keys(cfg.trusted)) and cfg.sources["trusted_keys"] == "both"


def test_switched_off_nothing_can_be_changed_and_nothing_registered_is_used(setup, monkeypatch):
    as_(setup["alice"])
    client.post("/v1/portability/setup/repositories",
                json={"name": "escrow-gh", "url": "https://github.com/o/r.git", "confirm": True})
    assert "escrow-gh" in service.config().repositories
    monkeypatch.setenv("ARGUS_PORTABILITY_UI_CONFIG", "off")
    refused = client.post("/v1/portability/setup/repositories",
                          json={"name": "another", "url": "https://github.com/o/r2.git", "confirm": True})
    assert refused.status_code == 403 and refused.json()["detail"]["code"] == "ui_config_off"
    assert "escrow-gh" not in service.config().repositories
    assert client.get("/v1/portability/setup").json()["enabled"] is False
    assert client.get("/v1/portability/config").json()["ui_config"]["enabled"] is False


def test_with_separation_of_duties_another_administrator_approves(setup, monkeypatch):
    monkeypatch.setenv("ARGUS_PORTABILITY_POLICY_SEPARATION_OF_DUTIES", "1")
    as_(setup["alice"])
    r = client.post("/v1/portability/setup/repositories",
                    json={"name": "escrow-gh", "url": "https://github.com/o/r.git", "confirm": True}).json()
    assert r["status"] == "pending" and "escrow-gh" not in service.config().repositories
    mine = client.post("/v1/portability/setup/approve", json={"kind": "repository", "id": "escrow-gh", "confirm": True})
    assert mine.status_code == 403
    as_(setup["bob"])
    assert client.post("/v1/portability/setup/approve",
                       json={"kind": "repository", "id": "escrow-gh", "confirm": True}).json()["status"] == "active"
    assert "escrow-gh" in service.config().repositories
    db = setup["db"]
    kinds = [e.kind for e in db.scalars(select(PortabilityEvent).where(PortabilityEvent.subject_id == "repository:escrow-gh")
                                        .order_by(PortabilityEvent.seq))]
    assert kinds[-2:] == ["repository_added", "approved"]


def test_only_an_administrator_signed_in_recently_changes_it(setup):
    plain = User(id=f"p-{uuid.uuid4().hex[:6]}", email="p@argus.test", is_admin=False)
    app.dependency_overrides[get_identity] = lambda: OidcIdentity(user=plain, claims={"auth_time": time.time()})
    assert client.get("/v1/portability/setup").status_code == 403
    stale = setup["alice"]
    app.dependency_overrides[get_identity] = lambda: OidcIdentity(user=stale, claims={"auth_time": time.time() - 7200})
    r = client.post("/v1/portability/setup/repositories",
                    json={"name": "escrow-gh", "url": "https://github.com/o/r.git", "confirm": False})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "step_up_required"


# --- the whole way: an export signed and published, and imported, with only what was set up here --------

from tests.test_portability import dbs, env, populate, run_export, run_import  # noqa: E402,F401


def test_an_export_and_its_import_run_on_the_set_up_made_in_the_web_app(setup, dbs, env):  # noqa: F811
    from app.portability import gitrepo
    db = setup["db"]
    base = service.config()
    repo = gitrepo.init_bare(setup["root"] / "escrow-web.git")
    ui_config.add_repository(db, base, "alice", name="escrow-web", url=str(repo))
    key = ui_config.generate_signing_key(db, base, "alice", "argus-test")
    db.commit()

    deployment_cfg = env.cfg

    def web_cfg(name, decrypt=True):
        """The tests' installation with no repository, signing key or trusted keys of its own."""
        cfg = deployment_cfg(name, decrypt)
        cfg.signer, cfg.trusted, cfg.repositories = None, None, {}
        return ui_config.merged(cfg)
    env.cfg = web_cfg

    src, dst = dbs(), dbs()
    s = populate(src, env.tmp)
    view, manifest = run_export(src, env, s, repository="escrow-web")
    assert view["state"] == "published" and view["labels"]["signed"]
    assert manifest["signature"]["key_id"] == key["key_id"]
    _, reconciliation = run_import(dst, env, view["git"]["tag"], repository="escrow-web")
    assert reconciliation["passed"]


def test_the_data_can_travel_in_the_repository_with_no_artifact_store_on_either_side(setup, dbs, env):  # noqa: F811
    """Chosen as the artifact store, the repository carries the export's data files in the signed commit, and
    the importing installation reads them from it: nothing else to copy between installations."""
    import json as _json

    from sqlalchemy.orm import Session as _Session

    from app.models.portability import PortabilityExport
    from app.portability import gitrepo
    db = setup["db"]
    repo = gitrepo.init_bare(setup["root"] / "escrow-data.git")
    ui_config.add_repository(db, service.config(), "alice", name="escrow-data", url=str(repo))
    ui_config.generate_signing_key(db, service.config(), "alice", "argus-test")
    db.commit()
    deployment_cfg = env.cfg

    def web_cfg(name, decrypt=True):
        cfg = deployment_cfg(name, decrypt)
        cfg.signer, cfg.trusted, cfg.repositories, cfg.stores = None, None, {}, {}
        return ui_config.merged(cfg)
    env.cfg = web_cfg

    src, dst = dbs(), dbs()
    s = populate(src, env.tmp)
    cfg = env.cfg("src")
    with _Session(src) as sdb:
        exp = service.create_export(sdb, "alice@example.org", mode="workspace", workspaces=[s.ws, s.inv],
                                    classifications=[], decisions={"opaque_blobs": "approve_opaque"}, cfg=cfg,
                                    destination={"repository": "escrow-data", "artifact_store": service.REPOSITORY_STORE})
        service.analyse_export(sdb, exp, "alice@example.org", cfg)
        service.approve_export(sdb, exp, "bob@example.org", admin=True, fresh_auth=True, cfg=cfg)
        sdb.commit()
        service.generate_export(src, sdb, exp, "bob@example.org", cfg, fresh_auth=True)
        service.publish_export(sdb, exp, "bob@example.org", cfg)
        sdb.commit()
        view = service.export_view(sdb.get(PortabilityExport, exp.id))
    assert view["state"] == "published", view.get("error")
    files = subprocess.run(["git", "--git-dir", repo, "ls-tree", "-r", "--name-only", view["git"]["tag"]],
                           capture_output=True, text=True).stdout.splitlines()
    data = [f for f in files if f.startswith("artifacts/sha256/")]
    blobs = (cfg.export_dir(exp.id) / "blobs.manifest.ndjson").read_text().splitlines()
    assert data and len(data) >= len(blobs)                    # every attachment and source content is in it
    assert all(_json.loads(b)["locator"].startswith("argus-artifacts://escrow-data/") for b in blobs)
    _, reconciliation = run_import(dst, env, view["git"]["tag"], repository="escrow-data")
    assert reconciliation["passed"]


def test_an_artifact_store_registered_here_is_a_directory_in_the_portability_area(setup, monkeypatch):
    as_(setup["alice"])
    r = client.post("/v1/portability/setup/stores", json={"name": "vault", "note": "local copies", "confirm": True})
    assert r.status_code == 201 and r.json()["path"].startswith(str(setup["root"]))
    cfg = service.config()
    assert cfg.stores["vault"].root == setup["root"] / "stores" / "vault" and cfg.sources["stores"]["vault"] == "web"
    assert client.get("/v1/portability/config").json()["repository_store"] == "@repository"
    monkeypatch.setenv("ARGUS_PORTABILITY_ARTIFACT_STORES", f"vault-dev={setup['root'] / 'dev'}")
    assert client.post("/v1/portability/setup/stores", json={"name": "vault-dev", "confirm": True}).status_code == 409
    assert client.post("/v1/portability/setup/stores/vault/remove", json={"confirm": True}).status_code == 204
    assert "vault" not in service.config().stores


def test_a_registered_repository_and_a_trusted_key_can_be_changed(setup, monkeypatch, tmp_path):
    as_(setup["alice"])
    client.post("/v1/portability/setup/repositories",
                json={"name": "escrow", "url": "git@github.com:infn-argus/old.git", "confirm": True})
    client.post("/v1/portability/setup/repositories/escrow/host-keys/confirm",
                json={"fingerprints": [HOST_KEYS[0]["fingerprint"]], "confirm": True})
    same_host = client.post("/v1/portability/setup/repositories/escrow",
                            json={"url": "git@github.com:infn-argus/new.git", "confirm": True}).json()
    assert same_host["url"].endswith("new.git") and same_host["usable"]         # same server: still confirmed
    moved = client.post("/v1/portability/setup/repositories/escrow",
                        json={"url": "ssh://git@baltig.infn.it/argus/escrow.git", "provider": "gitlab",
                              "confirm": True}).json()
    assert moved["provider"] == "gitlab" and not moved["host_keys_confirmed"] and not moved["usable"]
    other_kind = client.post("/v1/portability/setup/repositories/escrow",
                             json={"url": "https://github.com/infn-argus/escrow.git", "confirm": True})
    assert other_kind.status_code == 422
    other = signing.new_key(tmp_path / "k")
    key = client.post("/v1/portability/setup/trusted-keys",
                      json={"line": signing.allowed_signers_line(other), "confirm": True}).json()
    noted = client.post(f"/v1/portability/setup/trusted-keys/{key['id']}/note",
                        json={"note": "the laptop", "confirm": True}).json()
    assert noted["note"] == "the laptop"
    monkeypatch.setenv("ARGUS_PORTABILITY_POLICY_SEPARATION_OF_DUTIES", "1")
    client.post("/v1/portability/setup/repositories/escrow/host-keys/confirm",
                json={"fingerprints": [HOST_KEYS[0]["fingerprint"]], "confirm": True})
    changed = client.post("/v1/portability/setup/repositories/escrow",
                          json={"url": "ssh://git@baltig.infn.it/argus/escrow2.git", "confirm": True}).json()
    assert changed["status"] == "pending"                                         # a change is approved again
