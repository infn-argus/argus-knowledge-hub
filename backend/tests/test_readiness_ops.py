"""Operational readiness (asset-model-revision §19 items 9, 10 and 13): an
export loads into an empty instance with nothing lost; a backup restores and
checks itself; the performance probe measures the targets."""
import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db import DATABASE_URL, SessionLocal
from app.ledger import engine, ops, portability, service
from app.main import app
from app.models.asset import Relation
from app.models.attachment import Attachment
from app.models.issue import Issue, IssueComment
from app.services.visibility import NONE, set_current_grants
from tests.test_ledger_slice import Slice
from tests.test_ledger_transition import token

client = TestClient(app)
BACKEND = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not DATABASE_URL.startswith("postgresql"), reason="needs Postgres")


def _url(name: str) -> str:
    return DATABASE_URL.rsplit("/", 1)[0] + f"/{name}"


@pytest.fixture()
def empty_instance():
    """A brand-new database at the current migration head."""
    name = f"argus_empty_{secrets.token_hex(4)}"
    admin = create_engine(_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    env = {**os.environ, "DATABASE_URL": _url(name)}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    yield _url(name)
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()


def populated(tmp_path) -> Slice:
    s = Slice()
    db = SessionLocal()
    s.config_rev(db)
    s.inventory(db)
    service.edit_value(db, s.inv, "rossi", s.unit(db).uid, "attr:argus_location", "Rack B13")
    issue = Issue(uid=str(uuid.uuid4()), workspace_id=s.inv, title="Pump noisy", asset_uid=s.unit(db).uid,
                  attributes={"argus_source": "jira", "argus_source_key": "SPARC-9"})
    db.add(issue)
    db.flush()
    db.add(IssueComment(uid=str(uuid.uuid4()), issue_uid=issue.uid, author="rossi", body="replaced the gasket"))
    db.add(Relation(workspace_id=s.inv, from_asset_uid=s.unit(db, "84321").uid,
                    to_asset_uid=s.unit(db, "90001").uid, relation_type="spare for"))
    photo = tmp_path / "files" / "photo.jpg"
    photo.parent.mkdir()
    photo.write_bytes(b"a photo of the pump")
    db.add(Attachment(uid=str(uuid.uuid4()), workspace_id=s.inv, issue_uid=issue.uid, filename="photo.jpg",
                      file_size=19, storage_path=str(photo)))
    db.commit()
    db.close()
    return s


def test_an_export_loads_into_an_empty_instance_with_nothing_lost(tmp_path, empty_instance):
    s = populated(tmp_path)
    db = SessionLocal()
    portability.everything()
    try:
        counts = portability.write_bundle(db, s.inv, str(tmp_path / "bundle"))
        source = portability.fingerprint(db, s.inv)
    finally:
        set_current_grants(NONE)
        db.close()
    assert counts["assets"] == 2 and counts["tickets"] == 1 and counts["attachments"] == 1 and counts["ledger"] > 0

    bundle = portability.read_bundle(str(tmp_path / "bundle"))
    assert portability.verify_files(bundle, str(tmp_path / "files")) == []
    target = create_engine(empty_instance)
    try:
        with Session(target) as other:
            portability.load_bundle(other, bundle, str(tmp_path / "files"))
            other.commit()
            portability.everything()
            try:
                loaded = portability.fingerprint(other, s.inv)
            finally:
                set_current_grants(NONE)
            with pytest.raises(ValueError):
                portability.load_bundle(other, bundle)          # not twice into the same instance
    finally:
        target.dispose()
    assert loaded == source


def test_a_backup_restores_into_a_scratch_database_and_checks_itself(tmp_path, empty_instance):
    s = populated(tmp_path)
    db = SessionLocal()
    portability.everything()
    try:
        portability.write_bundle(db, s.inv, str(tmp_path / "bundle"))
    finally:
        set_current_grants(NONE)
        db.close()
    target = create_engine(empty_instance)
    with Session(target) as other:
        portability.load_bundle(other, portability.read_bundle(str(tmp_path / "bundle")), str(tmp_path / "files"))
        other.commit()
    target.dispose()

    manifest = ops.backup(empty_instance, str(tmp_path / "backups"), str(tmp_path / "files"))
    assert manifest["counts"]["assets"] == 2 and manifest["attachments_sha256"]
    manifest_file = next((tmp_path / "backups").glob("*.manifest.json"))
    report = ops.rehearse_restore(empty_instance, str(manifest_file))
    assert report["ok"], report
    assert report["checks"] == {"dump_checksum": True, "counts_match": True, "audit_chain": True}


def test_the_probe_measures_the_targets(tmp_path):
    s = populated(tmp_path)
    db = SessionLocal()
    headers = token(db, s.inv)
    db.commit()
    uids = [s.unit(db, "84321").uid, s.unit(db, "90001").uid]
    result = ops.probe(client, headers, uids, ["pump", "84321"], edit_uid=uids[1], db=db, workspace_id=s.inv)
    db.close()
    assert set(result["meets"]) == {"record_page_p95_ms", "search_p95_ms", "own_edit_visible_ms", "reprojection_s"}
    assert result["own_edit_visible_ms"] is not None
    assert result["record_page_p95_ms"] > 0 and result["samples"]["record_page"] == 2
