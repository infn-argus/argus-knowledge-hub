"""Erasing a record leaves no dangling link: its tickets say what they were about, the documents that described
it stop pointing at nothing, and the count of what hangs on it is given before."""
import secrets

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.document import DocumentRelation
from app.models.issue import IssueHistory
from app.models.workspace import Workspace
from tests.test_ledger_transition import token

client = TestClient(app)


def test_deleting_a_record_tells_its_tickets_and_unlinks_its_documents():
    ws = f"del-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name=ws))
    db.flush()
    h = token(db, ws)
    from app.ledger import engine
    from app.models.asset import Asset
    from app.models.document import Document
    from app.models.issue import Issue
    uid, tid, did = (f"{k}-{ws}" for k in ("a", "t", "d"))
    db.add(Asset(uid=uid, workspace_id=ws, schema_uid=engine.ensure_type(db, ws, "Equipment").uid, key=f"PUMP-{ws}",
                 name="Pump", type="Equipment", attributes={}))
    db.flush()
    db.add(Issue(uid=tid, workspace_id=ws, title="Pump leaks", asset_uid=uid))
    db.add(Document(uid=did, workspace_id=ws, code=f"DOC-{ws}", title="Pump manual"))
    db.flush()
    db.add(DocumentRelation(workspace_id=ws, from_document_uid=did, to_type="asset", to_uid=uid,
                            relation_type="describes"))
    db.commit()
    db.close()
    hangs = client.get(f"/v1/assets/{uid}/dependents", headers=h).json()
    assert (hangs["tickets"], hangs["open_tickets"], hangs["documents"]) == (1, 1, 1)
    assert client.delete(f"/v1/assets/{uid}", headers=h).status_code == 204
    db = SessionLocal()
    try:
        from sqlalchemy import select
        assert not list(db.scalars(select(DocumentRelation).where(DocumentRelation.to_uid == uid)))
        said = [x for x in db.scalars(select(IssueHistory).where(IssueHistory.issue_uid == tid))
                if x.field == "Object"]
        assert said and said[0].to_value == "deleted" and "Pump" in said[0].from_value
    finally:
        db.close()


def test_a_place_stated_in_the_ledger_is_not_derived_a_second_time():
    """A record made on the form with "Located in" showed its rack twice: once stated, once derived from the
    same value."""
    from sqlalchemy import select
    from app.ledger import engine
    from app.models.asset import Asset, Relation
    ws = f"loc-{secrets.token_hex(3)}"
    db = SessionLocal()
    try:
        db.add(Workspace(id=ws, name=ws))
        db.flush()
        rack = Asset(uid=f"r-{ws}", workspace_id=ws, schema_uid=engine.ensure_type(db, ws, "Rack").uid,
                     key=f"RACK-{ws}", name=f"Rack {ws}", type="Rack", attributes={})
        unit = Asset(uid=f"u-{ws}", workspace_id=ws, schema_uid=engine.ensure_type(db, ws, "Equipment").uid,
                     key=f"UNIT-{ws}", name="Unit", type="Equipment", attributes={"argus_location": rack.key})
        db.add_all([rack, unit])
        db.flush()
        engine.derive_located_in(db, [ws])
        edges = lambda: [r.derivation for r in db.scalars(select(Relation).where(  # noqa: E731
            Relation.from_asset_uid == unit.uid, Relation.relation_type == "located in"))]
        assert edges() == ["derived"]
        db.add(Relation(workspace_id=ws, from_asset_uid=unit.uid, to_asset_uid=rack.uid, relation_type="located in",
                        derivation="ledger", rule="t"))
        db.flush()
        engine.derive_located_in(db, [ws])
        assert edges() == ["ledger"]
    finally:
        db.rollback()
        db.close()
