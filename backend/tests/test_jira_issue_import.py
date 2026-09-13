"""Importing Jira issues as tickets.

The mapping that needs care is status: Jira lets every project define its
own workflow, so the names can't be trusted, but each status carries one
of three statusCategory values — too coarse on its own, because "Closed"
and "Resolved" both land in "done", and "Pending" and "In Progress" both
land in "indeterminate". Names decide where they're unambiguous, the
category catches everything else.
"""
import json
import secrets
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models.asset import Asset
from app.models.asset_subresources import AssetTicket
from app.models.import_job import ImportJob
from app.models.issue import Issue, IssueComment
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services.jira_issue_import import map_priority, map_state, run_jira_issue_import


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


def _status(name, category):
    return {"name": name, "statusCategory": {"key": category}}


def test_status_name_wins_where_it_is_unambiguous():
    # Both are "done" to Jira; they are different states to us.
    assert map_state(_status("Closed", "done")) == "closed"
    assert map_state(_status("Resolved", "done")) == "resolved"
    # Both are "indeterminate"; likewise.
    assert map_state(_status("In Progress", "indeterminate")) == "in_progress"
    assert map_state(_status("Waiting for customer", "indeterminate")) == "pending"
    # Italian workflows are in use on this tracker.
    assert map_state(_status("Chiuso", "done")) == "closed"
    assert map_state(_status("In corso", "indeterminate")) == "in_progress"


def test_unknown_status_falls_back_to_its_category():
    """A project with a bespoke workflow still has to land somewhere
    sensible rather than defaulting everything to "new"."""
    assert map_state(_status("Awaiting triage by SOC", "new")) == "new"
    assert map_state(_status("Escalated to vendor", "indeterminate")) == "in_progress"
    assert map_state(_status("Shipped", "done")) == "resolved"
    assert map_state({}) == "new"


def test_priority_covers_both_jira_schemes():
    assert map_priority({"name": "Blocker"}) == "blocker"
    assert map_priority({"name": "Highest"}) == "critical"
    assert map_priority({"name": "Major"}) == "high"
    assert map_priority({"name": "Trivial"}) == "low"
    assert map_priority({"name": "Media"}) == "medium"
    assert map_priority(None) is None
    assert map_priority({"name": "Wibble"}) is None


class _JiraStub(BaseHTTPRequestHandler):
    issues: list = []
    comments: dict = {}

    def log_message(self, *args):
        pass

    def _json(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/rest/api/2/search":
            query = parse_qs(parsed.query)
            start = int(query.get("startAt", ["0"])[0])
            size = int(query.get("maxResults", ["100"])[0])
            page = self.issues[start:start + size]
            self._json({"total": len(self.issues), "startAt": start, "issues": page})
        elif parsed.path.endswith("/comment"):
            key = parsed.path.split("/")[-2]
            self._json({"comments": self.comments.get(key, [])})
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture()
def jira_stub():
    server = HTTPServer(("127.0.0.1", 0), _JiraStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _issue(key, summary, status, category, **fields):
    base = {
        "key": key,
        "fields": {
            "summary": summary,
            "description": fields.get("description"),
            "status": _status(status, category),
            "priority": fields.get("priority"),
            "assignee": fields.get("assignee"),
            "reporter": fields.get("reporter"),
            "labels": fields.get("labels", []),
            "duedate": fields.get("duedate"),
            "resolutiondate": fields.get("resolutiondate"),
            "updated": fields.get("updated", "2026-09-01T10:00:00.000+0000"),
            "issuetype": {"name": fields.get("issuetype", "Task")},
            "project": {"key": fields.get("project", "LNF")},
            "components": [{"name": c} for c in fields.get("components", [])],
        },
    }
    return base


def _run(workspace_id, base_url, **kwargs):
    db = SessionLocal()
    job = ImportJob(uid=str(uuid.uuid4()), workspace_id=workspace_id, source="jira-issues")
    db.add(job)
    db.commit()
    job_uid = job.uid
    db.close()
    run_jira_issue_import(job_uid, workspace_id, base_url, "pat", "project = LNF", **kwargs)
    db = SessionLocal()
    job = db.get(ImportJob, job_uid)
    result = (job.status, job.error, dict(job.counts or {}))
    db.close()
    return result


def test_imports_issues_with_comments_and_is_idempotent(jira_stub):
    _server, base_url = jira_stub
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"

    _JiraStub.issues = [
        _issue(f"LNF-{suffix}-1", "Camera offline", "In Progress", "indeterminate",
               priority={"name": "Major"}, assignee={"displayName": "Giulia Bianchi"},
               reporter={"displayName": "Marco Rossi"}, labels=["vacuum"],
               components=["Controls"]),
        _issue(f"LNF-{suffix}-2", "Replace pump", "Closed", "done",
               priority={"name": "Low"}, resolutiondate="2026-08-20T09:00:00.000+0000"),
    ]
    _JiraStub.comments = {
        f"LNF-{suffix}-1": [
            {"id": "1", "author": {"displayName": "Marco Rossi"}, "body": "Looking into it"},
            {"id": "2", "author": "mrossi", "body": "Rebooted"},
        ]
    }

    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.commit()
    db.close()

    status, error, counts = _run(ws, base_url)
    assert status == "succeeded", error
    assert counts["tickets"] == 2
    assert counts["comments"] == 2

    db = SessionLocal()
    first = db.get(Issue, f"{ws}:LNF-{suffix}-1")
    assert first.title == "Camera offline"
    assert first.state == "in_progress"
    assert first.priority == "high"
    assert first.assignee == "Giulia Bianchi"
    assert first.created_by == "Marco Rossi"
    assert first.labels == ["vacuum"]
    assert first.attributes["jiraKey"] == f"LNF-{suffix}-1"
    assert first.attributes["jiraUrl"].endswith(f"/browse/LNF-{suffix}-1")
    assert first.attributes["jiraComponents"] == ["Controls"]
    # The plain-string author shape, which crashed the asset importer once.
    authors = {c.author for c in db.scalars(
        select(IssueComment).where(IssueComment.issue_uid == first.uid)
    )}
    assert authors == {"Marco Rossi", "mrossi"}

    second = db.get(Issue, f"{ws}:LNF-{suffix}-2")
    assert second.state == "closed"
    assert second.closed_at is not None
    db.close()

    # Re-running must not duplicate comments or tickets.
    status, error, counts = _run(ws, base_url)
    assert status == "succeeded", error
    assert counts["comments"] == 0, "second run should add no new comments"
    db = SessionLocal()
    assert db.scalar(select(Issue).where(Issue.uid == f"{ws}:LNF-{suffix}-1")) is not None
    assert len(db.scalars(select(IssueComment).where(
        IssueComment.issue_uid == f"{ws}:LNF-{suffix}-1")).all()) == 2
    db.close()


def test_pagination_fetches_every_page(jira_stub):
    _server, base_url = jira_stub
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"
    # More than one page at the importer's page size.
    _JiraStub.issues = [
        _issue(f"LNF-{suffix}-{n}", f"Issue {n}", "Open", "new") for n in range(250)
    ]
    _JiraStub.comments = {}

    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.commit()
    db.close()

    status, error, counts = _run(ws, base_url)
    assert status == "succeeded", error
    assert counts["tickets"] == 250

    db = SessionLocal()
    assert len(db.scalars(select(Issue).where(Issue.workspace_id == ws)).all()) == 250
    db.close()


def test_a_ticket_naming_an_asset_key_is_linked_to_it(jira_stub):
    """What makes having tickets and equipment in one place worth anything:
    "LNFT2-145356 is offline" becomes a real link to that camera."""
    _server, base_url = jira_stub
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"
    asset_key = f"LNFT2-{secrets.randbelow(900000) + 100000}"

    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.flush()
    db.add(Schema(uid=f"sc-{suffix}", workspace_id=ws, name="Cameras"))
    db.flush()
    db.add(Asset(uid=f"as-{suffix}", workspace_id=ws, schema_uid=f"sc-{suffix}",
                 key=asset_key, name="FI4-B-CAM-VIS-001", type="Cameras"))
    db.commit()
    db.close()

    _JiraStub.issues = [
        _issue(f"LNF-{suffix}-1", f"{asset_key} is offline", "Open", "new",
               description="Seen during the run."),
        # A key-shaped string that matches no asset must not link anything.
        _issue(f"LNF-{suffix}-2", "Unrelated ABC-999 mention", "Open", "new"),
    ]
    _JiraStub.comments = {}

    status, error, counts = _run(ws, base_url)
    assert status == "succeeded", error
    assert counts["asset_links"] == 1

    db = SessionLocal()
    linked = db.get(Issue, f"{ws}:LNF-{suffix}-1")
    assert linked.asset_uid == f"as-{suffix}"
    tickets = db.scalars(select(AssetTicket).where(AssetTicket.asset_uid == f"as-{suffix}")).all()
    assert [t.ticket_key for t in tickets] == [f"LNF-{suffix}-1"]
    assert db.get(Issue, f"{ws}:LNF-{suffix}-2").asset_uid is None
    db.close()


def test_link_assets_can_be_turned_off(jira_stub):
    _server, base_url = jira_stub
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"
    asset_key = f"LNFT3-{secrets.randbelow(900000) + 100000}"

    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.flush()
    db.add(Schema(uid=f"sc-{suffix}", workspace_id=ws, name="Cameras"))
    db.flush()
    db.add(Asset(uid=f"as-{suffix}", workspace_id=ws, schema_uid=f"sc-{suffix}",
                 key=asset_key, name="Cam", type="Cameras"))
    db.commit()
    db.close()

    _JiraStub.issues = [_issue(f"LNF-{suffix}-1", f"{asset_key} broken", "Open", "new")]
    _JiraStub.comments = {}

    status, error, counts = _run(ws, base_url, link_assets=False)
    assert status == "succeeded", error
    assert counts.get("asset_links", 0) == 0
    db = SessionLocal()
    assert db.get(Issue, f"{ws}:LNF-{suffix}-1").asset_uid is None
    db.close()


def test_a_failing_search_marks_the_job_failed(jira_stub):
    """A broken JQL or a rejected token has to surface, not look like an
    import that found nothing."""
    _server, base_url = jira_stub
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.commit()
    db.close()

    status, error, _counts = _run(ws, base_url + "/wrong-prefix")
    assert status == "failed"
    assert "Jira search failed" in (error or "")
