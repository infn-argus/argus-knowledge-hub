"""The hub as an MCP server.

Two things are being checked. That the protocol handshake is the one a
client actually performs — initialize, the initialized notification,
tools/list, tools/call — because a server that is subtly wrong there
simply never appears in the assistant, with no error anybody sees. And
that the tools answer the question the project exists to answer: what
else touches this equipment.
"""
import json
import secrets

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_token
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models.api_token import ApiToken
from app.models.asset import Asset, Relation
from app.models.document import Document, DocumentRevision
from app.models.issue import Issue
from app.models.llm_config import LLMConfig
from app.models.schema import Schema
from app.models.workspace import Workspace

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def world():
    """A camera in a rack, a fault about it, and a procedure covering it."""
    suffix = secrets.token_hex(4)
    ws = f"mcp-{suffix}"
    ids = {
        "ws": ws,
        "camera": f"cam-{suffix}",
        "rack": f"rack-{suffix}",
        "ticket": f"tk-{suffix}",
        "document": f"doc-{suffix}",
        "key": f"LNFT2-{secrets.randbelow(900000) + 100000}",
    }
    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.flush()
    raw = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=ws, token_hash=hash_token(raw)))
    db.add(Schema(uid=f"sc-{suffix}", workspace_id=ws, name="Cameras", applies_to="objects"))
    db.add(Schema(uid=f"dt-{suffix}", workspace_id=ws, name="Procedure",
                  applies_to="documents"))
    db.flush()
    db.add(Asset(uid=ids["camera"], workspace_id=ws, schema_uid=f"sc-{suffix}",
                 key=ids["key"], name="FI4-B-CAM-VIS-001", type="Cameras"))
    db.add(Asset(uid=ids["rack"], workspace_id=ws, schema_uid=f"sc-{suffix}",
                 key=f"LNFR-{suffix}", name="Rack BTF-B12", type="Cameras"))
    db.flush()
    db.add(Relation(workspace_id=ws, from_asset_uid=ids["camera"],
                    to_asset_uid=ids["rack"], relation_type="mounted in"))
    db.add(Issue(uid=ids["ticket"], workspace_id=ws, title="Camera drops frames",
                 state="in_progress", asset_uid=ids["camera"],
                 attributes={"argus_root_cause": "A failed PoE injector."}))
    document = Document(uid=ids["document"], workspace_id=ws, code=f"PROC-{suffix}",
                        title="Camera replacement", document_type_uid=f"dt-{suffix}")
    db.add(document)
    db.flush()
    revision = DocumentRevision(uid=f"rev-{suffix}", document_uid=document.uid,
                                revision_number=1, state="published",
                                body_markdown="# Camera replacement\n\nSteps.")
    db.add(revision)
    db.flush()
    document.current_revision_uid = revision.uid
    db.commit()
    db.close()
    return ids, raw


def auth(raw: str) -> dict:
    return {"Authorization": f"Bearer {raw}"}


def rpc(raw: str, method: str, params: dict | None = None, request_id: int | None = 1):
    payload: dict = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        payload["id"] = request_id
    if params is not None:
        payload["params"] = params
    return client.post("/mcp", json=payload, headers=auth(raw))


def tool(raw: str, name: str, arguments: dict | None = None) -> dict:
    resp = rpc(raw, "tools/call", {"name": name, "arguments": arguments or {}})
    assert resp.status_code == 200, resp.text
    body = resp.json()["result"]
    assert body["isError"] is False, body
    return json.loads(body["content"][0]["text"])


# --- the handshake ------------------------------------------------------

def test_initialize_answers_with_a_protocol_and_tools_capability(world):
    _ids, raw = world
    result = rpc(raw, "initialize", {"protocolVersion": "2025-06-18"}).json()["result"]
    assert "protocolVersion" in result
    assert result["capabilities"]["tools"] is not None
    assert result["serverInfo"]["name"] == "argus-knowledge-hub"


def test_the_initialized_notification_is_accepted_with_no_body(world):
    """A notification has no id and expects no answer; replying to one is
    how a client ends up waiting for ever."""
    _ids, raw = world
    resp = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=auth(raw),
    )
    assert resp.status_code == 202
    assert resp.content in (b"", b"null")


def test_tools_are_listed_with_schemas_and_no_python_internals(world):
    _ids, raw = world
    tools = rpc(raw, "tools/list").json()["result"]["tools"]
    names = {t["name"] for t in tools}
    assert {"search_objects", "get_object", "graph_neighbours", "get_document"} <= names
    for t in tools:
        assert "handler" not in t, "the Python callable must not be serialised"
        assert t["inputSchema"]["type"] == "object"


def test_an_unknown_method_is_refused_not_ignored(world):
    _ids, raw = world
    body = rpc(raw, "resources/list").json()
    assert body["error"]["code"] == -32601


def test_an_unknown_tool_is_refused(world):
    _ids, raw = world
    body = rpc(raw, "tools/call", {"name": "delete_everything", "arguments": {}}).json()
    assert body["error"]["code"] == -32602


def test_the_server_needs_a_token(world):
    resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert resp.status_code == 401


def test_get_is_refused_because_there_is_nothing_to_stream(world):
    _ids, raw = world
    assert client.get("/mcp", headers=auth(raw)).status_code == 405


# --- the tools ----------------------------------------------------------

def test_an_object_is_found_by_key_or_by_name(world):
    ids, raw = world
    by_key = tool(raw, "get_object", {"uid_or_key": ids["key"]})
    assert by_key["found"] and by_key["uid"] == ids["camera"]
    found = tool(raw, "search_objects", {"query": "FI4-B-CAM"})
    assert ids["camera"] in [o["uid"] for o in found["objects"]]


def test_an_object_carries_what_it_is_connected_to(world):
    ids, raw = world
    result = tool(raw, "get_object", {"uid_or_key": ids["camera"]})
    assert [r["object"]["uid"] for r in result["relations"]] == [ids["rack"]]
    assert result["relations"][0]["relation"] == "mounted in"


def test_the_graph_answers_what_else_touches_this_camera(world):
    """The question RAG cannot answer, and the reason this server exists."""
    ids, raw = world
    graph = tool(raw, "graph_neighbours",
                 {"kind": "asset", "uid": ids["camera"], "depth": 1})
    reached = {(n["kind"], n["uid"]) for n in graph["nodes"]}
    assert ("ticket", ids["ticket"]) in reached
    assert ("asset", ids["rack"]) in reached


def test_a_ticket_carries_its_root_cause(world):
    ids, raw = world
    result = tool(raw, "get_ticket", {"uid": ids["ticket"]})
    assert result["root_cause"] == "A failed PoE injector."


def test_a_document_comes_back_as_markdown(world):
    ids, raw = world
    result = tool(raw, "get_document", {"uid_or_code": ids["document"]})
    assert result["found"]
    assert "# Camera replacement" in result["body_markdown"]


def test_a_missing_record_says_so_rather_than_failing(world):
    _ids, raw = world
    assert tool(raw, "get_object", {"uid_or_key": "nothing-like-this"})["found"] is False


def test_another_workspace_is_not_reachable(world):
    """The token is the workspace: the tools must not see past it."""
    ids, _raw = world
    other = f"other-{secrets.token_hex(4)}"
    db = SessionLocal()
    db.add(Workspace(id=other, name="Other"))
    db.flush()
    raw_other = secrets.token_urlsafe(16)
    db.add(ApiToken(workspace_id=other, token_hash=hash_token(raw_other)))
    db.commit()
    db.close()

    assert tool(raw_other, "get_object", {"uid_or_key": ids["camera"]})["found"] is False
    assert tool(raw_other, "search_objects", {})["total"] == 0


# --- confidentiality ----------------------------------------------------

def test_a_confidential_document_is_withheld_by_default(world):
    """The consumer on the other end of a tool call is a model, so the
    switch that governs sending text to one governs this too."""
    ids, raw = world
    db = SessionLocal()
    document = db.get(Document, ids["document"])
    document.confidentiality = "riservato"
    db.commit()
    db.close()

    assert tool(raw, "get_document", {"uid_or_code": ids["document"]})["found"] is False
    assert tool(raw, "search_documents", {})["total"] == 0


def test_a_confidential_document_is_returned_where_the_workspace_allows_it(world):
    ids, raw = world
    db = SessionLocal()
    db.get(Document, ids["document"]).confidentiality = "riservato"
    db.add(LLMConfig(workspace_id=ids["ws"], base_url="https://x/v1", model="m",
                     enabled=True, last_check_ok=True, allow_confidential=True))
    db.commit()
    db.close()

    assert tool(raw, "get_document", {"uid_or_code": ids["document"]})["found"] is True
