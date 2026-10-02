"""Ask ARGUS and the MCP tools find a kind of equipment by its types.

"Can you list me magnets?" got "there are no objects of type magnet" from a beamline with 79: they are
Quadrupoles, Dipoles, Correctors…, none called Magnet, and the search matched the word against names and
one exact type. The tools now take several types with their subtypes, count per type, list the type
catalogue, and suggest the types whose descriptions mention a word no type is called.
"""
import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_token
from app.db import SessionLocal
from app.main import app
from app.models.api_token import ApiToken
from app.models.asset import Asset
from app.models.schema import Schema
from app.models.workspace import Workspace

client = TestClient(app)


@pytest.fixture()
def beamline():
    t = secrets.token_hex(4)
    ws, other = f"ask-{t}", f"ask-other-{t}"
    db = SessionLocal()
    db.add_all([Workspace(id=ws, name="Beamline"), Workspace(id=other, name="Other")])
    db.flush()
    raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=ws, token_hash=hash_token(raw)))
    sc = lambda name, desc, parent=None, abstract=False, shared=False, owner=ws: Schema(  # noqa: E731
        uid=f"{owner}:{name}", workspace_id=owner, name=name, description=desc, applies_to="objects",
        parent_schema_uid=parent, is_concrete=not abstract, is_global=shared)
    # The other workspace's Quadrupole type is shared, as a catalogue's is; its objects are not.
    db.add_all([
        sc("Beam Element", "Part of the lattice.", abstract=True),
        sc("Power Supply", "Powers a magnet or another load."),
        sc("Control Network", "A network the control system uses."),
        sc("Shared Quadrupole", "A focusing magnet, shared.", shared=True, owner=other),
    ])
    db.flush()
    db.add_all([sc("Quadrupole", "A focusing magnet.", parent=f"{ws}:Beam Element"),
                sc("Dipole", "A bending magnet.", parent=f"{ws}:Beam Element")])
    db.flush()

    def obj(name, type_name, owner=ws, schema=None):
        db.add(Asset(uid=f"{owner}-{name}", workspace_id=owner, schema_uid=schema or f"{owner}:{type_name}",
                     key=f"{owner}:{name}", name=name, type=type_name))

    for n in ("QUA01", "QUA02", "QUA03"):
        obj(n, "Quadrupole")
    obj("DIP01", "Dipole")
    obj("PS01", "Power Supply")
    obj("sparc-magnets", "Control Network")
    obj("THEIRS01", "Shared Quadrupole", owner=other)
    db.commit()
    db.close()
    yield {"ws": ws, "other": other, "raw": raw}
    db = SessionLocal()
    from app.ledger.audit import allow_purge
    for w in (ws, other):
        allow_purge(db)
        db.delete(db.get(Workspace, w))
        db.commit()
    db.close()


def tool(raw, name, arguments=None):
    import json
    resp = client.post("/mcp", headers={"Authorization": f"Bearer {raw}"},
                       json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": name, "arguments": arguments or {}}})
    body = resp.json()["result"]
    assert body["isError"] is False, body
    return json.loads(body["content"][0]["text"])


def test_a_type_includes_its_subtypes_and_the_answer_counts_per_type(beamline):
    found = tool(beamline["raw"], "search_objects", {"types": ["beam element"]})
    assert found["total"] == 4 and found["by_type"] == {"Quadrupole": 3, "Dipole": 1}
    plural = tool(beamline["raw"], "search_objects", {"types": ["Quadrupoles", "dipole"]})
    assert plural["by_type"] == {"Quadrupole": 3, "Dipole": 1}


def test_a_word_no_type_is_called_suggests_the_types_that_describe_it(beamline):
    found = tool(beamline["raw"], "search_objects", {"query": "magnets"})
    # Only the network called sparc-magnets matches by name, and that is said, with what to try instead.
    assert found["by_type"] == {"Control Network": 1}
    suggested = {t["name"] for t in found["types_whose_description_mentions_it"]}
    assert {"Quadrupole", "Dipole"} <= suggested and "Control Network" not in suggested
    assert "by name only" in found["hint"]


def test_the_type_catalogue_answers_which_types_a_kind_is(beamline):
    listed = {t["name"]: t for t in tool(beamline["raw"], "list_types", {"query": "magnet"})["types"]}
    assert {"Quadrupole", "Dipole", "Power Supply"} <= set(listed)
    assert listed["Quadrupole"]["description"] == "A focusing magnet." and listed["Quadrupole"]["records"] == 3
    every = {t["name"] for t in tool(beamline["raw"], "list_types")["types"]}
    assert "Beam Element" in every                     # a parent with records below it


def test_an_object_of_a_shared_type_is_not_shared(beamline):
    """Every beamline's pumps are of the catalogue's shared type; the pumps stay each beamline's own. The
    search used to treat any object of a shared type as visible everywhere."""
    found = tool(beamline["raw"], "search_objects", {"query": "THEIRS01"})
    assert found["total"] == 0
