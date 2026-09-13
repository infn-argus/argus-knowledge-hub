"""Walking the graph.

The question this exists to answer is the one an operator actually asks:
"this camera is down — what else does it touch, what broke it before,
which procedure covers it". That crosses four tables, and the point of
the traversal is that the caller doesn't have to know which.
"""
import secrets
import uuid
from datetime import datetime, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.models.asset import Asset, Relation
from app.models.asset_subresources import AssetTicket
from app.models.document import Document, DocumentRelation
from app.models.group import Group, GroupMember
from app.models.issue import Issue, IssueLink
from app.models.schema import Schema
from app.models.user import User
from app.models.workspace import Workspace
from app.services.knowledge_graph import graph_summary, traverse


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def world():
    """A camera in a rack, a ticket about it linked to an epic, and a
    procedure that documents it — one of each kind of edge."""
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"
    # Ids are plain strings from the start: reading them off ORM objects
    # after the session closes detaches them and fails.
    ids = {
        "ws": ws,
        "camera": f"cam-{suffix}", "rack": f"rack-{suffix}",
        "ticket": f"tk-{suffix}", "epic": f"epic-{suffix}",
        "document": f"doc-{suffix}", "group": f"g-{suffix}", "user": f"u-{suffix}",
    }
    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.flush()
    db.add(Schema(uid=f"sc-{suffix}", workspace_id=ws, name="Cameras"))
    db.flush()

    camera = Asset(uid=f"cam-{suffix}", workspace_id=ws, schema_uid=f"sc-{suffix}",
                   key=f"LNFT2-{suffix}", name="FI4-B-CAM-VIS-001", type="Cameras")
    rack = Asset(uid=f"rack-{suffix}", workspace_id=ws, schema_uid=f"sc-{suffix}",
                 key=f"LNFR-{suffix}", name="Rack B12", type="Racks")
    db.add_all([camera, rack])
    db.flush()
    db.add(Relation(workspace_id=ws, from_asset_uid=ids["camera"], to_asset_uid=ids["rack"],
                    relation_type="mounted_in"))

    ticket = Issue(uid=f"tk-{suffix}", workspace_id=ws, title="Camera offline",
                   state="in_progress", asset_uid=ids["camera"],
                   attributes={"argus_source_key": f"LNFDCS-{suffix}"})
    epic = Issue(uid=f"epic-{suffix}", workspace_id=ws, title="BTF refurbishment",
                 state="new", attributes={"argus_source_key": f"LNFDCS-E{suffix}"})
    db.add_all([ticket, epic])
    db.flush()
    now = datetime.now(timezone.utc)
    db.add(AssetTicket(uid=str(uuid.uuid4()), asset_uid=ids["camera"],
                       ticket_key=f"LNFDCS-{suffix}", summary="Camera offline",
                       type="affects", status="in_progress", created=now, updated=now))
    db.add(IssueLink(from_issue_uid=ids["ticket"], to_issue_uid=ids["epic"],
                     relation_type="epic", created_at=now))

    procedure = Document(uid=f"doc-{suffix}", workspace_id=ws, code=f"PROC-{suffix}",
                         title="Camera replacement procedure")
    db.add(procedure)
    db.flush()
    db.add(DocumentRelation(workspace_id=ws, from_document_uid=ids["document"],
                            to_type="asset", to_uid=ids["camera"], relation_type="describes"))

    group = Group(uid=f"g-{suffix}", name="Servizio Laser", source="ldap")
    user = User(id=f"u-{suffix}", email=f"u-{suffix}@infn.it", name="Giulia Bianchi")
    db.add_all([group, user])
    db.flush()
    db.add(GroupMember(group_uid=ids["group"], user_id=ids["user"], source="ldap"))
    db.commit()
    db.close()

    return ids


def test_one_hop_from_an_object_reaches_every_kind(world):
    db = SessionLocal()
    graph = traverse(db, world["ws"], "asset", world["camera"], depth=1)
    db.close()

    kinds = {(n.kind, n.uid) for n in graph.nodes}
    assert ("asset", world["rack"]) in kinds, "the rack it is mounted in"
    assert ("ticket", world["ticket"]) in kinds, "the ticket about it"
    assert ("document", world["document"]) in kinds, "the procedure covering it"
    # The epic is two hops away, through the ticket.
    assert ("ticket", world["epic"]) not in kinds

    vias = {e.via for e in graph.edges}
    assert vias == {"structure", "work", "documentation"}


def test_a_second_hop_reaches_the_epic(world):
    db = SessionLocal()
    graph = traverse(db, world["ws"], "asset", world["camera"], depth=2)
    db.close()

    by_uid = {n.uid: n for n in graph.nodes}
    assert world["epic"] in by_uid
    assert by_uid[world["epic"]].depth == 2
    assert by_uid[world["ticket"]].depth == 1


def test_the_walk_is_the_same_from_either_end(world):
    """A question about a magnet has to find the ticket that names it, not
    only the other way round."""
    db = SessionLocal()
    from_asset = traverse(db, world["ws"], "asset", world["camera"], depth=1)
    from_ticket = traverse(db, world["ws"], "ticket", world["ticket"], depth=1)
    db.close()

    assert any(n.uid == world["ticket"] for n in from_asset.nodes)
    assert any(n.uid == world["camera"] for n in from_ticket.nodes)


def test_kinds_filter_narrows_the_answer(world):
    db = SessionLocal()
    graph = traverse(db, world["ws"], "asset", world["camera"], depth=2, kinds=["document"])
    db.close()

    assert {n.kind for n in graph.nodes} == {"asset", "document"}
    assert any(n.uid == world["document"] for n in graph.nodes)


def test_people_are_reachable_through_their_group(world):
    db = SessionLocal()
    graph = traverse(db, world["ws"], "group", world["group"], depth=1)
    db.close()
    assert any(n.kind == "person" and n.uid == world["user"] for n in graph.nodes)


def test_another_workspaces_node_is_not_traversable(world):
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    db.add(Workspace(id=f"other-{suffix}", name="Other"))
    db.commit()
    graph = traverse(db, f"other-{suffix}", "asset", world["camera"], depth=1)
    db.close()
    assert graph.nodes == []


def test_the_cap_is_reported_rather_than_silently_applied(world):
    db = SessionLocal()
    graph = traverse(db, world["ws"], "asset", world["camera"], depth=3, max_nodes=2)
    db.close()
    assert graph.truncated is True
    assert len(graph.nodes) <= 2


def test_summary_counts_nodes_and_edges(world):
    db = SessionLocal()
    summary = graph_summary(db, world["ws"])
    db.close()

    assert summary["nodes"]["assets"] == 2
    assert summary["nodes"]["tickets"] == 2
    assert summary["nodes"]["documents"] == 1
    assert summary["edges"]["asset_to_asset"] == 1
    assert summary["edges"]["ticket_to_ticket"] == 1
    # The fixture's ticket names the camera twice over — a subject field and
    # a link row carrying its key — and that is one connection, not two.
    assert summary["edges"]["ticket_to_asset"] == 1
    assert summary["edges"]["document_to_anything"] == 1


def test_a_ticket_naming_its_object_directly_still_counts(world):
    """Tickets written here carry their object in the subject field and have
    no link row at all; a summary that counted only link rows would report a
    workspace full of work as having none."""
    suffix = secrets.token_hex(4)
    ws = f"only-subject-{suffix}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="Subject only"))
    db.flush()
    db.add(Schema(uid=f"sc2-{suffix}", workspace_id=ws, name="Magnets"))
    db.flush()
    db.add(Asset(uid=f"mag-{suffix}", workspace_id=ws, schema_uid=f"sc2-{suffix}",
                 key=f"LNFM-{suffix}", name="QUAD-BTF-03", type="Magnets"))
    db.flush()
    db.add(Issue(uid=f"tk2-{suffix}", workspace_id=ws, title="Trips at 180 A",
                 state="new", asset_uid=f"mag-{suffix}"))
    db.commit()

    summary = graph_summary(db, ws)
    db.close()
    assert summary["edges"]["ticket_to_asset"] == 1
