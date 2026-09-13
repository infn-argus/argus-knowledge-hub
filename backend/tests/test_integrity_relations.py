"""A resolved reference and a Relation row are two separate facts, and only
the second one feeds an object's Inbound/Outbound panel.

Production shape: a camera in the EUAPS workspace references a workgroup, a
facility and a location owned by the (globally shared) Divisione Acceleratori
workspace. The attribute values resolved and rendered normally, yet the object
showed "Outbound: none / Inbound: none" — the import's key -> uid map was
scoped to the importing workspace, so every cross-workspace pair was silently
skipped, and relink only ever rewrote values without materializing relations.
"""
import secrets

import pytest

from app.db import Base, SessionLocal, engine
from app.models.asset import Asset, Relation
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services.integrity import relink_workspace


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


def _setup_cross_workspace_camera(db, suffix):
    """A camera in EUAPS whose "Owner" attribute holds the Jira display label
    of a workgroup owned by another workspace and shared via its type."""
    ws_shared, ws_own = f"divacc-{suffix}", f"euaps-{suffix}"
    workgroup_schema, camera_schema = f"wg-{suffix}", f"cam-{suffix}"
    workgroup_uid, camera_uid = f"wg-obj-{suffix}", f"cam-obj-{suffix}"

    db.add(Workspace(id=ws_shared, name="Divisione Acceleratori", is_global=True))
    db.add(Workspace(id=ws_own, name="EUAPS"))
    db.flush()
    db.add(Schema(uid=workgroup_schema, workspace_id=ws_shared, name="Workgroup", is_global=True))
    db.add(Schema(
        uid=camera_schema, workspace_id=ws_own, name="Cameras",
        attributes=[{
            "id": "1", "key": "owner", "name": "Owner", "type": "reference",
            "referenceSchemaUid": workgroup_schema,
        }],
    ))
    db.flush()
    db.add(Asset(
        uid=workgroup_uid, workspace_id=ws_shared, schema_uid=workgroup_schema,
        key=f"LNFT1-{suffix}", name="Servizio Laser", type="Workgroup",
    ))
    db.add(Asset(
        uid=camera_uid, workspace_id=ws_own, schema_uid=camera_schema,
        key=f"LNFT2-{suffix}", name="FI4-B-CAM-VIS-001", type="Cameras",
        attributes={"owner": "Servizio Laser"},
    ))
    db.commit()
    return ws_own, camera_uid, workgroup_uid


def test_relink_creates_relations_across_workspaces():
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    ws_own, camera_uid, workgroup_uid = _setup_cross_workspace_camera(db, suffix)

    stats = relink_workspace(db, ws_own)
    assert stats["values_relinked"] == 1
    assert stats["relations_created"] == 1
    db.close()

    db = SessionLocal()
    relation = db.query(Relation).filter(Relation.from_asset_uid == camera_uid).one()
    assert relation.to_asset_uid == workgroup_uid
    assert relation.relation_type == "Owner"
    # The Relation row belongs to the workspace that created it, not to the
    # workspace that owns the target.
    assert relation.workspace_id == ws_own

    # Both cached lists have to be refreshed, including the target's — it
    # lives in another workspace, which relink doesn't otherwise walk.
    assert db.get(Asset, camera_uid).outbound_relations == [workgroup_uid]
    assert db.get(Asset, workgroup_uid).inbound_relations == [camera_uid]
    db.close()


def test_relink_is_idempotent_and_keeps_manual_relations():
    """Re-running relink (every import now ends with one) must not duplicate
    relations, and must not touch relations a person added by hand."""
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    ws_own, camera_uid, workgroup_uid = _setup_cross_workspace_camera(db, suffix)
    db.add(Relation(
        workspace_id=ws_own, from_asset_uid=camera_uid,
        to_asset_uid=workgroup_uid, relation_type="related_to",
    ))
    db.commit()

    relink_workspace(db, ws_own)
    second = relink_workspace(db, ws_own)
    assert second["relations_created"] == 0
    assert second["values_relinked"] == 0
    db.close()

    db = SessionLocal()
    types = sorted(
        r.relation_type
        for r in db.query(Relation).filter(Relation.from_asset_uid == camera_uid)
    )
    assert types == ["Owner", "related_to"]
    db.close()
