"""The whole chain an EPIK8s configuration implies, as import options: the controllers between lines and
what they run, the converters' ports in the IT workspace, the inventory linked instead of duplicated, and
the AI's proposals for the channels no rule recognises."""
import json
import secrets
import uuid

import pytest

from app.db import SessionLocal
from app.ledger import control_binding
from app.ledger import service
from app.models.asset import Asset, Relation
from app.models.import_job import ImportJob
from app.models.llm_config import LLMConfig
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services import asset_types as at
from app.services import epik8s_import

CONFIG = """
beamline: BEAMLINE
iocDefaults:
  agilent-vac: {devgroup: vac, devtype: ipcmini, devfunc: ion}
  tpg: {devgroup: vac, devtype: tpg366}
  odd: {devgroup: xyz, template: odd}
epicsConfiguration:
  iocs:
    vac-ipc:
      iocprefix: EUAPS:VAC
      template: agilent-vac
      iocparam: [{name: server, value: scflameprmxavac002.lnf.infn.it}, {name: port, value: 4003}]
      devices: [{name: GUNSIP01, channel: 1}, {name: GUNSIP02, channel: 2}]
    vgc-tpg366-fi-01:
      iocprefix: EUAPS:VAC
      template: tpg
      iocparam: [{name: server, value: scflameprmxavac002.lnf.infn.it}, {name: port, value: 4004}]
      devices: [{name: FI31VUG01, channel: 1}, {name: FI32VUG01, channel: 2}]
    odd-ioc:
      iocprefix: EUAPS:ODD
      template: odd
      devices: [{name: ZZZ01}]
"""


@pytest.fixture()
def world(monkeypatch):
    t = secrets.token_hex(3)
    tag, ws, it = f"T{t}".upper(), f"chain-{t}", f"chain-it-{t}"
    db = SessionLocal()
    db.add_all([Workspace(id=w, name=w) for w in (ws, it)])
    db.flush()
    at.ensure_asset_types(db, ws)
    gauge_type = db.query(Schema).filter(Schema.workspace_id == ws, Schema.name == "Vacuum Gauge").one()
    # The inventory already holds one of the gauges, under its tag.
    inv = str(uuid.uuid4())
    service.create_record(db, ws, "test", uid=inv, schema_uid=gauge_type.uid, key=f"INV-{t}", name="FI31-V-VUG-FR-001",
                          type_name="Vacuum Gauge", attributes={})
    db.add(LLMConfig(workspace_id=ws, base_url="https://gateway.example/v1", model="m-1", enabled=True,
                     last_check_ok=True))
    db.commit()
    db.close()
    monkeypatch.setattr(epik8s_import, "_fetch", lambda *a, **k: CONFIG.replace("BEAMLINE", tag))
    monkeypatch.setattr(epik8s_import, "_resolve_commit", lambda *a, **k: "abc123")
    yield {"tag": tag, "ws": ws, "it": it, "inv": inv}
    db = SessionLocal()
    from app.ledger.audit import allow_purge
    for w in (ws, it):
        allow_purge(db)
        db.delete(db.get(Workspace, w))
        db.commit()
    db.query(LLMConfig).filter(LLMConfig.workspace_id == ws).delete()
    db.commit()
    db.close()


def run(w, **options):
    db = SessionLocal()
    uid = str(uuid.uuid4())
    db.add(ImportJob(uid=uid, workspace_id=w["ws"], source="epik8s"))
    db.commit()
    db.close()
    epik8s_import.run_epik8s_import(uid, w["ws"], "github", "https://git.example/x", None, **options)
    db = SessionLocal()
    job = db.get(ImportJob, uid)
    assert job.status == "completed", job.error
    counts = dict(job.counts)
    db.close()
    return counts


def names_and_edges(ws_ids):
    db = SessionLocal()
    names = {a.uid: a.name for a in db.query(Asset)}
    edges = {(names.get(r.from_asset_uid), r.relation_type, names.get(r.to_asset_uid))
             for r in db.query(Relation).filter(Relation.workspace_id.in_(ws_ids))}
    db.close()
    return edges


def test_controllers_ports_and_the_inventory_first(world):
    w = world
    counts = run(w, infer_elements=True, infer_controllers=True, link_inventory=True, it_workspace=w["it"])
    assert counts["inferred_controllers"] == 2 and counts["linked_to_inventory"] == 1
    assert counts["ports"] == 2 and counts["inventory_link_proposals"] == 1
    e = names_and_edges([w["ws"], w["it"]])
    # The IPCMini powers the two ion pumps and is reached through the Moxa's Access Point.
    assert ("vac-ipc controller", "powers", "GUNSIP01 Ion Pump") in e
    assert ("vac-ipc controller", "reached through", "scflameprmxavac002") in e
    # The TPG 366 powers the gauge it got inferred; the other one is the inventory's, linked by proposal.
    assert ("vgc-tpg366-fi-01 controller", "powers", "FI32VUG01 Vacuum Gauge") in e
    assert not any(n == "FI31VUG01 Vacuum Gauge" for _, _, n in e)                     # no inferred twin
    pending = SessionLocal()
    proposals = control_binding.proposals(pending, w["ws"])
    pending.close()
    assert {(p["subject"]["name"], p["target"]["name"]) for p in proposals} == {("FI31VUG01", "FI31-V-VUG-FR-001")}
    # The Moxa's ports, in the IT workspace: 4003 is P3, 4004 is P4.
    assert ("scflameprmxavac002 P3", "port of", "scflameprmxavac002") in e
    assert ("scflameprmxavac002 P4", "port of", "scflameprmxavac002") in e
    db = SessionLocal()
    ctl = db.query(Asset).filter(Asset.workspace_id == w["ws"], Asset.name == "vgc-tpg366-fi-01 controller").one()
    assert ctl.type == "Vacuum Controller" and ctl.attributes["model"] == "TPG 366" and ctl.attributes["n_channels"] == 2
    db.close()
    # A second read changes nothing.
    again = run(w, infer_elements=True, infer_controllers=True, link_inventory=True, it_workspace=w["it"])
    assert again["ports"] == 2
    assert names_and_edges([w["ws"], w["it"]]) == e


def test_the_ai_proposes_what_unrecognised_channels_drive_and_nothing_is_confirmed(world, monkeypatch):
    w = world
    seen = []

    def complete(endpoint, system, user, max_tokens=512, extra=None):
        seen.append(user)
        return json.dumps({"channels": [{"id": 1, "type": "Chiller", "confidence": 0.7, "reason": "odd cooling unit"}]})

    monkeypatch.setattr("app.services.llm.complete", complete)
    counts = run(w, infer_elements=True, ai_unrecognised=True)
    assert counts["ai_asked"] == 1 and counts["ai_proposed"] == 1
    assert "ZZZ01" in seen[0] and "GUNSIP01" not in seen[0]                         # only what no rule knew
    db = SessionLocal()
    unit = db.query(Asset).filter(Asset.workspace_id == w["ws"], Asset.name == "ZZZ01 Chiller").one()
    assert unit.type == "Chiller" and unit.record_status == "Provisional"            # a proposal, not a record
    device = db.query(Asset).filter(Asset.workspace_id == w["ws"], Asset.name == "ZZZ01").one()
    assert db.query(Relation).filter(Relation.from_asset_uid == device.uid,
                                     Relation.relation_type == "acts on").count() == 0
    db.close()
