"""Keys made by the hub: a record created without one gets the next key from
its workspace's pattern, a typed key is kept, and the type follows the schema."""
import secrets
import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.ledger import engine
from app.main import app
from app.models.workspace import Workspace
from app.services import asset_keys
from tests.test_ledger_transition import token

client = TestClient(app)


def setup(pattern=None):
    w = f"key-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=w, name=w, asset_key_pattern=pattern))
    db.flush()
    types = {t: engine.ensure_type(db, w, t).uid for t in ("Ion Pump", "Quadrupole")}
    headers = token(db, w)
    db.commit()
    db.close()
    return w, headers, types


def create(headers, schema_uid, **extra):
    return client.post("/v1/assets", headers=headers, json={
        "uid": str(uuid.uuid4()), "schema_uid": schema_uid, "name": "x", "attributes": {}, **extra})


def test_blank_key_follows_the_default_pattern_per_type():
    w, headers, types = setup()
    W = w.upper()
    preview = client.get(f"/v1/assets/next-key?schema_uid={types['Ion Pump']}", headers=headers)
    assert preview.status_code == 200 and preview.json()["key"] == f"{W}-IP-0001"
    assert create(headers, types["Ion Pump"]).json()["key"] == f"{W}-IP-0001"
    assert create(headers, types["Ion Pump"], key="").json()["key"] == f"{W}-IP-0002"
    assert create(headers, types["Quadrupole"]).json()["key"] == f"{W}-QUA-0001"


def test_a_used_number_is_skipped_and_a_typed_key_kept():
    w, headers, types = setup("{WS}-{SEQ:3}")
    W = w.upper()
    assert create(headers, types["Ion Pump"], key=f"{W}-002").json()["key"] == f"{W}-002"
    assert create(headers, types["Ion Pump"]).json()["key"] == f"{W}-001"
    assert create(headers, types["Quadrupole"]).json()["key"] == f"{W}-003"
    assert create(headers, types["Ion Pump"], key=f"{W}-003").status_code == 409


def test_the_type_is_the_schema_name_whatever_is_sent():
    _, headers, types = setup()
    r = create(headers, types["Ion Pump"], type="Something else")
    assert r.status_code == 201 and r.json()["type"] == "Ion Pump"


def test_pattern_validation():
    assert asset_keys.validate_pattern("{WS}-{TYPE}-{SEQ:4}")
    for bad in ("{WS}-{TYPE}", "{SEQ}-{SEQ}", "{WS}-{FOO}-{SEQ}", "{WS:3}-{SEQ}", "{WS} {SEQ}"):
        try:
            asset_keys.validate_pattern(bad)
        except asset_keys.KeyPatternError:
            continue
        raise AssertionError(f"accepted {bad}")
