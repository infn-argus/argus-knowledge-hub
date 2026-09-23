"""Sharing across workspaces: the graph, and documents.

The installation this is for keeps device models and shared procedures in
one global workspace and gives every beamline its own. That only works if
what is marked global is reachable from the workspace asking — and the
knowledge graph, which is where root-cause questions are actually answered,
was the one place that did not honour the flag.
"""
import secrets

import pytest

from app.db import Base, SessionLocal, engine
from app.models.asset import Asset, Relation
from app.models.document import Document, DocumentRevision
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services.knowledge_graph import load_node, traverse


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def world():
    """A global workspace holding a camera model, and a beamline holding a
    camera that is an instance of it."""
    suffix = secrets.token_hex(4)
    ids = {
        "global_ws": f"global-{suffix}",
        "beamline": f"euaps-{suffix}",
        "other": f"sparc-{suffix}",
        "model": f"model-{suffix}",
        "camera": f"cam-{suffix}",
        "private": f"priv-{suffix}",
        "procedure": f"proc-{suffix}",
    }
    db = SessionLocal()
    db.add(Workspace(id=ids["global_ws"], name="Global", is_global=True))
    db.add(Workspace(id=ids["beamline"], name="EUAPS"))
    db.add(Workspace(id=ids["other"], name="SPARC"))
    db.flush()
    db.add(Schema(uid=f"sm-{suffix}", workspace_id=ids["global_ws"], name="Device Models",
                  applies_to="objects", is_global=True))
    db.add(Schema(uid=f"sc-{suffix}", workspace_id=ids["beamline"], name="Control Devices",
                  applies_to="objects"))
    db.add(Schema(uid=f"so-{suffix}", workspace_id=ids["other"], name="Control Devices",
                  applies_to="objects"))
    db.flush()
    db.add(Asset(uid=ids["model"], workspace_id=ids["global_ws"], schema_uid=f"sm-{suffix}",
                 key=f"MOD-{suffix}", name="Basler a2A2600-20gmBAS", type="Device Models",
                 is_global=True))
    db.add(Asset(uid=ids["camera"], workspace_id=ids["beamline"], schema_uid=f"sc-{suffix}",
                 key=f"EU-{suffix}", name="FI8-CAM-06", type="Control Devices"))
    db.add(Asset(uid=ids["private"], workspace_id=ids["other"], schema_uid=f"so-{suffix}",
                 key=f"SP-{suffix}", name="GUNSIP01", type="Control Devices"))
    db.flush()
    # The beamline's camera is an instance of the shared model.
    db.add(Relation(workspace_id=ids["beamline"], from_asset_uid=ids["camera"],
                    to_asset_uid=ids["model"], relation_type="instance of"))
    # And something links it to another beamline's private object, which the
    # graph must not draw.
    db.add(Relation(workspace_id=ids["beamline"], from_asset_uid=ids["camera"],
                    to_asset_uid=ids["private"], relation_type="see also"))

    document = Document(uid=ids["procedure"], workspace_id=ids["global_ws"],
                        code=f"PROC-{suffix}", title="Replacing an Agilent ion pump",
                        is_global=True)
    db.add(document)
    db.flush()
    revision = DocumentRevision(uid=f"rev-{suffix}", document_uid=document.uid,
                                revision_number=1, state="published",
                                body_markdown="Vent the sector first.")
    db.add(revision)
    db.flush()
    document.current_revision_uid = revision.uid
    db.commit()
    db.close()
    return ids


# --- the graph ----------------------------------------------------------

def test_a_global_model_is_reachable_from_the_beamline_that_uses_it(world):
    """The whole point of a shared model layer: from the camera you can see
    what model it is, in the view root-cause questions run on."""
    db = SessionLocal()
    graph = traverse(db, world["beamline"], "asset", world["camera"], depth=1)
    assert world["model"] in [n.uid for n in graph.nodes]
    assert "instance of" in [e.relation for e in graph.edges]
    db.close()


def test_another_workspaces_private_object_is_not_drawn(world):
    ids = world
    db = SessionLocal()
    graph = traverse(db, ids["beamline"], "asset", ids["camera"], depth=1)
    assert ids["private"] not in [n.uid for n in graph.nodes]
    db.close()


def test_an_edge_is_never_drawn_to_a_node_that_is_not_shown(world):
    """A relation to an invisible object used to be emitted as an edge with
    no node — naming a uid the caller cannot see, and rendering as a line
    into empty space."""
    ids = world
    db = SessionLocal()
    graph = traverse(db, ids["beamline"], "asset", ids["camera"], depth=2)
    shown = {(n.kind, n.uid) for n in graph.nodes}
    for edge in graph.edges:
        assert (edge.from_kind, edge.from_uid) in shown
        assert (edge.to_kind, edge.to_uid) in shown
    db.close()


def test_a_global_document_loads_as_a_node_from_another_workspace(world):
    db = SessionLocal()
    assert load_node(db, world["beamline"], "document", world["procedure"]) is not None
    db.close()


def test_a_private_object_still_does_not_load_from_elsewhere(world):
    db = SessionLocal()
    assert load_node(db, world["beamline"], "asset", world["private"]) is None
    db.close()


# --- an object of a global type is not global for that reason -----------

def test_an_object_of_a_global_type_is_not_visible_elsewhere_unless_it_is_flagged(world):
    """Types are shared; objects are shared only when flagged. The REST API, the graph and the tools
    apply the same rule, or they disagree about what exists."""
    ids = world
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    plain, flagged = f"plain-{suffix}", f"flagged-{suffix}"
    for uid, is_global in ((plain, False), (flagged, True)):
        db.add(Asset(uid=uid, workspace_id=ids["global_ws"], schema_uid=f"sm-{ids['model'][6:]}",
                     key=f"{uid.upper()}", name="Another model", type="Device Models", is_global=is_global))
    db.commit()
    assert load_node(db, ids["beamline"], "asset", plain) is None
    assert load_node(db, ids["beamline"], "asset", flagged) is not None
    db.close()


# --- documents through the tools ----------------------------------------

def test_a_shared_procedure_is_searchable_from_a_beamline(world):
    """The reason documents needed the flag: one procedure covers every
    beamline's Agilent pumps, and each beamline has to be able to find it."""
    from app.services.mcp_tools import search_documents, get_document
    db = SessionLocal()
    found = search_documents(db, world["beamline"], query="ion pump")
    assert world["procedure"] in [d["uid"] for d in found["documents"]]
    assert get_document(db, world["beamline"], world["procedure"])["found"] is True
    db.close()


def test_a_confidential_document_is_not_shared_even_when_marked_global(world):
    """"Confidential" and "readable by every workspace" cannot both be true,
    and the safe reading of that contradiction is the strict one."""
    from app.services.mcp_tools import get_document, search_documents
    db = SessionLocal()
    db.get(Document, world["procedure"]).confidentiality = "riservato"
    db.commit()

    found = search_documents(db, world["beamline"], query="ion pump")
    assert world["procedure"] not in [d["uid"] for d in found["documents"]]
    assert get_document(db, world["beamline"], world["procedure"])["found"] is False
    db.close()


def test_the_owning_workspace_still_reads_its_own_confidential_document(world):
    from app.services.mcp_tools import get_document
    from app.models.llm_config import LLMConfig
    db = SessionLocal()
    db.get(Document, world["procedure"]).confidentiality = "riservato"
    db.add(LLMConfig(workspace_id=world["global_ws"], base_url="https://x/v1",
                     model="m", enabled=True, last_check_ok=True, allow_confidential=True))
    db.commit()
    assert get_document(db, world["global_ws"], world["procedure"])["found"] is True
    db.close()


def test_a_global_model_is_searchable_from_a_beamline(world):
    """Consistency with the graph and the REST API: the tools an assistant
    calls must see the same objects a person does."""
    from app.services.mcp_tools import get_object, search_objects
    db = SessionLocal()
    found = search_objects(db, world["beamline"], query="Basler")
    assert world["model"] in [o["uid"] for o in found["objects"]]
    assert get_object(db, world["beamline"], world["model"])["found"] is True
    db.close()


def test_another_beamlines_object_is_still_not_searchable(world):
    from app.services.mcp_tools import get_object, search_objects
    db = SessionLocal()
    found = search_objects(db, world["beamline"], query="GUNSIP01")
    assert world["private"] not in [o["uid"] for o in found["objects"]]
    assert get_object(db, world["beamline"], world["private"])["found"] is False
    db.close()
