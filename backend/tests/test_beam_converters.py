"""Simulator files to the canonical beam model (app/beam_converters): MAD-X sequences, lines and TFS tables,
and Elegant lattices. The same ring written three ways must give the same model; the survey from lengths and
bends must close a ring; what a converter cannot read is said, not guessed; and a converted model imports.
"""
import math
from pathlib import Path

import pytest

from app import beam_converters as bc
from app.services import beam_model as bm

F = Path(__file__).parent / "fixtures" / "beam_model"
RING = ("dafne_accumulator.madx", "dafne_accumulator.lte", "dafne_accumulator_twiss.tfs")


def conv(name: str, **opts) -> dict:
    return bc.convert(name, (F / name).read_text(), bc.Options(**opts))


def test_the_same_ring_written_three_ways_is_one_model():
    docs = [conv(n, model_id="acc") for n in RING]
    orders = [d["paths"][0]["elements"] for d in docs]
    assert orders[0] == orders[1] == orders[2] and len(orders[0]) == 54
    counts = {}
    for e in docs[0]["elements"]:
        counts[e["type"]] = counts.get(e["type"], 0) + 1
    # The accumulator's own counts: what the layout of the real machine shows.
    assert counts == {"bpm": 12, "kicker": 4, "septum": 2, "corrector": 8, "dipole": 8, "quadrupole": 12, "sextupole": 8}
    for d in docs:
        assert d["paths"][0]["topology"] == "closed" and abs(d["paths"][0]["length"] - 32.56) < 1e-6
        v = d["datasets"][0]["values"]["QUAA101"]
        assert v["physics"]["k1"] == pytest.approx(4.30926) and v["physics"]["length"] == 0.3
        assert abs(v["s"] - docs[0]["datasets"][0]["values"]["QUAA101"]["s"]) < 1e-6
        bm.validate(d)                                                          # each is a valid canonical model


def test_the_survey_closes_a_ring_and_places_its_dipoles():
    d = conv("dafne_accumulator.madx")
    assert d["conversion"]["ring"] and d["conversion"]["survey_closure_m"] < 1e-6
    assert d["conversion"]["total_bend"] == pytest.approx(2 * math.pi)
    values = d["datasets"][0]["values"]
    # After the first quadrant the heading has turned 90°; a full turn brings it back.
    assert values["DIPA21"]["geometry"]["yaw"] == pytest.approx(math.pi / 2, abs=1e-6)
    assert values["SPTA1001"]["geometry"] == {"x": 0.0, "y": 0.0, "yaw": 0.0}


def test_madx_keeps_what_the_simulator_says_and_names_what_it_is():
    d = conv("dafne_accumulator.madx")
    by = {e["id"]: e for e in d["elements"]}
    assert by["KCKA1001"]["type"] == "kicker" and by["KCKA1001"]["native"] == {"source": "madx", "type": "HKICKER"}
    assert "pulsed" in by["KCKA1001"]["capabilities"] and "horizontal_steering" in by["KCKA1001"]["capabilities"]
    assert by["SPTA1001"]["type"] == "septum" and by["SPTA1001"]["native"]["type"] == "RBEND"
    assert by["CHV11"]["type"] == "corrector"
    assert {"horizontal_steering", "vertical_steering"} <= set(by["CHV11"]["capabilities"])
    assert by["BPSA11"]["observes"] == ["beam.position.x", "beam.position.y"]
    dip = d["datasets"][0]["values"]["DIPA11"]
    assert dip["physics"]["angle"] == pytest.approx(math.pi / 4) and dip["native"]["parameters"]["ANGLE"] == pytest.approx(math.pi / 4)
    beam = d["systems"][0]["beams"][0]["parameters"]
    assert beam["species"] == "electron" and beam["reference_energy"] == 0.51 and beam["charge"] == -1


def test_madx_language_variables_inheritance_refer_from_and_lines():
    text = """
    ! a transfer line, two ways
    lq := 0.2 * 2;  kf = 1.5;  kd = -kf;
    qf: quadrupole, l=lq, k1=kf;   qd: qf, k1=kd;      // qd inherits l from qf
    m1: monitor;
    bend: sbend, l=1.0, angle=0.1;
    tl: sequence, l=10, refer=entry;
      q1: qf, at=1;
      b1: bend, at=3;
      q2: qd, at=2, from=b1;
      m1, at=9;
    endsequence;
    cell: line=(qf, d1, qd, d1);
    d1: drift, l=0.5;
    arc: line=(2*cell, -(m1, bend));
    """
    seq = bc.convert("tl.madx", text, bc.Options(beamline="tl"))
    vals = seq["datasets"][0]["values"]
    assert seq["paths"][0]["elements"] == ["Q1", "B1", "Q2", "M1"] and seq["paths"][0]["topology"] == "open"
    assert vals["Q1"]["s"] == 1 and vals["Q2"]["s"] == 5                      # refer=entry; at 2 from b1 at 3
    assert vals["Q2"]["physics"] == {"length": 0.4, "k1": -1.5}               # inherited length, deferred lq
    line = bc.convert("tl.madx", text, bc.Options(beamline="arc"))
    assert line["paths"][0]["elements"] == ["QF", "QD", "QF#2", "QD#2", "BEND", "M1"]   # repeats, then reversed
    lv = line["datasets"][0]["values"]
    assert lv["QF#2"]["s"] == pytest.approx(1.8) and lv["BEND"]["s"] == pytest.approx(3.6)


def test_elegant_reads_rpn_and_continuations():
    text = """
    % 0.5 sto halfl
    Q1: KQUAD, L="halfl 2 *", &
        K1=8.2
    D1: DRIF, L=0.25
    B1: CSBEND, L=0.5, ANGLE="pi 18 /"
    W1: WATCH, FILENAME="w1.sdds"
    L1: LINE=(Q1, D1, B1, W1, D1, Q1)
    """
    d = bc.convert("x.lte", text)
    assert d["paths"][0]["elements"] == ["Q1", "B1", "Q1#2"]                  # drifts and watch points left out
    v = d["datasets"][0]["values"]
    assert v["Q1"]["physics"] == {"length": 1.0, "k1": 8.2} and v["B1"]["s"] == pytest.approx(1.25)
    assert v["B1"]["physics"]["angle"] == pytest.approx(math.pi / 18) and v["Q1#2"]["s"] == pytest.approx(2.0)
    with_markers = bc.convert("x.lte", text, bc.Options(keep_markers=True))
    assert "W1" in with_markers["paths"][0]["elements"]


@pytest.mark.parametrize("name, text, problem", [
    ("a.madx", "q: quadrupole, l=1;", "no SEQUENCE or LINE"),
    ("a.madx", "l: line=(q, nope);\nq: quadrupole, l=1;", "nope, which is not defined"),
    ("a.madx", "q: quadrupole, l=1, k1=1 +* 2;\nl: line=(q);", "cannot read the expression"),
    ("a.tfs", "@ NAME %s x\n* FOO BAR\n1 2", "needs the columns NAME and S"),
    ("a.xyz", "nothing a simulator wrote", "cannot tell which simulator"),
])
def test_what_cannot_be_read_is_said(name, text, problem):
    with pytest.raises(bc.ConversionError) as e:
        bc.convert(name, text)
    assert problem in str(e.value)


def test_a_converter_can_be_added():
    calls = []
    bc.register(bc.Converter(name="toy", label="Toy", extensions=(".toy",), detect=lambda t: t.startswith("TOY"),
                             convert=lambda text, filename, o: calls.append(filename) or conv("dafne_accumulator.madx")))
    try:
        assert bc.find("x.toy", "TOY").name == "toy"
        assert bc.convert("x.toy", "TOY")["paths"][0]["topology"] == "closed" and calls == ["x.toy"]
    finally:
        bc._REGISTRY.pop("toy")


def test_a_converted_file_imports_through_the_api(db_world):
    from tests.test_beam_model import client
    h = db_world
    formats = {f["name"] for f in client.get("/v1/beam-model/formats", headers=h).json()}
    assert {"argus", "madx", "madx-tfs", "elegant"} <= formats
    assert client.get("/v1/beam-model/schema", headers=h).json()["title"].startswith("ARGUS canonical beam model")
    out = client.post("/v1/beam-model/convert", headers=h, json={
        "filename": "dafne_accumulator_twiss.tfs", "content": (F / "dafne_accumulator_twiss.tfs").read_text(),
        "options": {"model_id": "acc-twiss", "system_kind": "Accumulator"}}).json()
    assert out["check"]["ok"] and out["report"]["ring"] and out["model"]["systems"][0]["kind"] == "Accumulator"
    done = client.post("/v1/beam-model/import", headers=h, json=out["model"])
    assert done.status_code == 200, done.text
    ring = next(p for p in client.get("/v1/beam-paths", headers=h).json() if p["name"] == "ACC")
    graph = client.get(f"/v1/beam-paths/{ring['uid']}/graph", headers=h).json()
    q = next(n for n in graph["nodes"] if n["name"] == "QUAA101")
    assert q["optics"]["beta_x"] > 0 and q["geometry"]["yaw"] is not None and graph["topology"] == "closed"
    dip = next(n for n in graph["nodes"] if n["name"] == "DIPA11")
    assert dip["angle"] == pytest.approx(math.pi / 4)
    bad = client.post("/v1/beam-model/convert", headers=h, json={"filename": "x.madx", "content": "q: quadrupole;"})
    assert bad.status_code == 422


@pytest.fixture()
def db_world():
    import secrets
    import uuid
    from app.auth import OidcIdentity, get_identity
    from app.db import SessionLocal
    from app.main import app
    from app.models.user import User
    from app.models.workspace import Workspace
    from app.services.asset_types import ensure_asset_types
    t = secrets.token_hex(4)
    ws = f"bmc-{t}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="Converters"))
    db.flush()
    ensure_asset_types(db, ws)
    admin = User(id=str(uuid.uuid4()), email=f"bmc-{t}@argus.test", is_admin=True)
    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.expunge(admin)
    db.close()
    app.dependency_overrides[get_identity] = lambda: OidcIdentity(user=admin)
    yield {"X-Workspace-Id": ws}
    app.dependency_overrides.pop(get_identity, None)
    db = SessionLocal()
    from app.ledger.audit import allow_purge
    allow_purge(db)
    db.delete(db.get(Workspace, ws))
    db.commit()
    db.close()
