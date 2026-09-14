"""Asking the hub a question.

The loop is what is tested, not the model: that a tool call is executed
and its result fed back in the shape the API requires, that every call is
returned to whoever asked — the whole point of the page — and that a
tool which fails is reported to the model rather than ending the
question.
"""
import json
import secrets

import pytest

from app.db import Base, SessionLocal, engine
from app.models.asset import Asset
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services.ask import MAX_ROUNDS, ask
from app.services.llm import Endpoint


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture()
def workspace():
    workspace_id = f"ask-{secrets.token_hex(4)}"
    db = SessionLocal()
    db.add(Workspace(id=workspace_id, name="WS"))
    db.flush()
    db.add(Schema(uid=f"{workspace_id}:cam", workspace_id=workspace_id,
                  name="Cameras", applies_to="objects"))
    db.flush()
    db.add(Asset(uid=f"a-{workspace_id}", workspace_id=workspace_id,
                 schema_uid=f"{workspace_id}:cam",
                 key=f"LNFT2-{secrets.randbelow(900000) + 100000}",
                 name="FI4-B-CAM-VIS-001", type="Cameras"))
    db.commit()
    db.close()
    return workspace_id


def scripted(monkeypatch, replies):
    """A model that says these things in turn, recording what it was sent."""
    sent = []

    def fake(endpoint, messages, tools=None, max_tokens=1200):
        sent.append([dict(m) for m in messages])
        return replies.pop(0)

    monkeypatch.setattr("app.services.ask.converse", fake)
    return sent


def tool_call(name, arguments, call_id="c1"):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)},
        }],
    }


def test_a_tool_call_is_executed_and_its_result_fed_back(workspace, monkeypatch):
    sent = scripted(monkeypatch, [
        tool_call("search_objects", {"query": "cameras"}),
        {"role": "assistant", "content": "One camera: FI4-B-CAM-VIS-001."},
    ])
    result = ask(SessionLocal(), workspace, Endpoint("https://x/v1", "m"), "What cameras?")

    assert result["answer"] == "One camera: FI4-B-CAM-VIS-001."
    assert result["stopped"] == "answered"
    # The second turn must carry the assistant's own message and a tool
    # message answering it, or the model is replying to nothing.
    roles = [m["role"] for m in sent[1]]
    assert roles == ["system", "user", "assistant", "tool"]
    assert "FI4-B-CAM-VIS-001" in sent[1][3]["content"]


def test_every_tool_call_is_returned_to_the_asker(workspace, monkeypatch):
    """The reason the page exists: an answer with no lookups behind it is
    the model talking about some other laboratory."""
    scripted(monkeypatch, [
        tool_call("search_objects", {"query": "cameras"}),
        {"role": "assistant", "content": "Done."},
    ])
    result = ask(SessionLocal(), workspace, Endpoint("https://x/v1", "m"), "q")

    assert [s["tool"] for s in result["steps"]] == ["search_objects"]
    assert result["steps"][0]["arguments"] == {"query": "cameras"}
    assert "FI4-B-CAM-VIS-001" in result["steps"][0]["result"]
    assert result["steps"][0]["error"] is None


def test_a_failing_tool_is_reported_to_the_model_not_raised(workspace, monkeypatch):
    """A model that omits a required argument gets told so and can retry,
    rather than the whole question dying on a TypeError."""
    sent = scripted(monkeypatch, [
        tool_call("get_object", {}),
        {"role": "assistant", "content": "I could not look that up."},
    ])
    result = ask(SessionLocal(), workspace, Endpoint("https://x/v1", "m"), "q")

    assert result["answer"] == "I could not look that up."
    assert result["steps"][0]["error"], "the failure should be recorded"
    assert sent[1][-1]["role"] == "tool", "and handed back for it to recover from"


def test_an_unknown_tool_does_not_end_the_question(workspace, monkeypatch):
    scripted(monkeypatch, [
        tool_call("delete_everything", {}),
        {"role": "assistant", "content": "No such thing."},
    ])
    result = ask(SessionLocal(), workspace, Endpoint("https://x/v1", "m"), "q")
    assert "No such tool" in result["steps"][0]["error"]


def test_arguments_the_tool_does_not_declare_are_dropped(workspace, monkeypatch):
    """A model passing workspace_id would otherwise reach past its own
    workspace — the tools take it from the token, never from the model."""
    scripted(monkeypatch, [
        tool_call("search_objects", {"query": "", "workspace_id": "somebody-else"}),
        {"role": "assistant", "content": "ok"},
    ])
    result = ask(SessionLocal(), workspace, Endpoint("https://x/v1", "m"), "q")
    assert result["steps"][0]["error"] is None
    assert "FI4-B-CAM-VIS-001" in result["steps"][0]["result"]


def test_a_model_that_loops_is_stopped_and_says_so(workspace, monkeypatch):
    scripted(monkeypatch, [
        tool_call("search_objects", {"query": "x"}, f"c{i}") for i in range(MAX_ROUNDS)
    ] + [{"role": "assistant", "content": "Here is what I found."}])
    result = ask(SessionLocal(), workspace, Endpoint("https://x/v1", "m"), "q")

    assert result["stopped"] == "exhausted"
    assert len(result["steps"]) == MAX_ROUNDS
    assert result["answer"] == "Here is what I found."


def test_malformed_arguments_do_not_crash_the_loop(workspace, monkeypatch):
    scripted(monkeypatch, [
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "c1", "type": "function",
            "function": {"name": "knowledge_summary", "arguments": "{not json"},
        }]},
        {"role": "assistant", "content": "ok"},
    ])
    result = ask(SessionLocal(), workspace, Endpoint("https://x/v1", "m"), "q")
    assert result["steps"][0]["arguments"] == {}
    assert result["steps"][0]["error"] is None
