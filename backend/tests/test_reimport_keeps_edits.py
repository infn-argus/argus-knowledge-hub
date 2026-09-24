"""A re-import updates what the configuration states and keeps what people changed.

The first version replaced an object's whole attribute bag on every run, so a
corrected value or a note somebody added disappeared at the next commit of the
configuration (asset-model-revision.md, C9). The importer now compares each
object with what it wrote last time (its import snapshot)."""
import secrets

import pytest
import yaml

from app.db import Base, SessionLocal, engine
from app.models.asset import Asset
from app.models.import_job import ImportJob
from app.models.workspace import Workspace
from app.services.epik8s_import import _Importer
from app.services.import_merge import effective_strategy
from tests.test_epik8s_import import VALUES_TEMPLATE


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def ws():
    ws = f"keep-{secrets.token_hex(4)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="Keep"))
    db.commit()
    db.close()
    return ws


@pytest.fixture()
def beamline():
    return f"k{secrets.token_hex(3)}"


def run(ws, beamline, mutate=None):
    values = yaml.safe_load(VALUES_TEMPLATE.replace("BEAMLINE", beamline))
    if mutate:
        mutate(values)
    db = SessionLocal()
    job = ImportJob(uid=f"job-{secrets.token_hex(4)}", workspace_id=ws, source="epik8s")
    db.add(job)
    db.commit()
    importer = _Importer(db, job, ws, "test@abc123:deploy/values.yaml")
    importer.ensure_types()
    importer.run(values, True)
    db.commit()
    return db, importer


def ioc(db, ws, name):
    return db.query(Asset).filter(Asset.workspace_id == ws, Asset.type == "IOC",
                                  Asset.name == name).one()


def edit(ws, name, **changes):
    db = SessionLocal()
    obj = ioc(db, ws, name)
    attrs = dict(obj.attributes)
    new_name = changes.pop("__name__", None)
    attrs.update(changes)
    obj.attributes = attrs
    if new_name:
        obj.name = new_name
    db.commit()
    db.close()


def test_a_corrected_value_survives_the_next_import(ws, beamline):
    db, _ = run(ws, beamline)
    assert ioc(db, ws, "vac-gunvpc").attributes["template"] == "agilent-vac"
    db.close()
    edit(ws, "vac-gunvpc", template="agilent-vac-corrected")

    db, importer = run(ws, beamline)
    assert ioc(db, ws, "vac-gunvpc").attributes["template"] == "agilent-vac-corrected"
    assert importer.counts.get("manual_edits_kept", 0) >= 1
    db.close()


def test_a_key_a_person_added_is_never_removed(ws, beamline):
    db, _ = run(ws, beamline)
    db.close()
    edit(ws, "vac-gunvpc", maintenance_note="bake-out done 2026-09")
    db, _ = run(ws, beamline)
    assert ioc(db, ws, "vac-gunvpc").attributes["maintenance_note"] == "bake-out done 2026-09"
    db.close()


def test_what_the_source_stops_stating_goes_unless_somebody_changed_it(ws, beamline):
    db, _ = run(ws, beamline)
    db.close()

    def drop_templates(values):
        for entry in values["epicsConfiguration"]["iocs"]:
            entry.pop("template", None)

    edit(ws, "vac-kly01vpc", template="kept-by-hand")
    db, _ = run(ws, beamline, drop_templates)
    assert ioc(db, ws, "vac-gunvpc").attributes.get("template") is None
    assert ioc(db, ws, "vac-kly01vpc").attributes["template"] == "kept-by-hand"
    db.close()


def test_the_source_still_updates_values_nobody_touched(ws, beamline):
    db, _ = run(ws, beamline)
    db.close()

    def new_template(values):
        values["epicsConfiguration"]["iocs"][0]["template"] = "agilent-vac-v2"

    db, _ = run(ws, beamline, new_template)
    assert ioc(db, ws, "vac-gunvpc").attributes["template"] == "agilent-vac-v2"
    db.close()


def test_provenance_records_the_revision(ws, beamline):
    db, _ = run(ws, beamline)
    assert ioc(db, ws, "vac-gunvpc").attributes["argus_source_ref"] == "test@abc123:deploy/values.yaml"
    db.close()


def test_the_destructive_strategy_is_retired():
    strategy, note = effective_strategy("remove_all_before")
    assert strategy == "override" and "nothing was deleted" in note
    assert effective_strategy("no_override") == ("no_override", None)
