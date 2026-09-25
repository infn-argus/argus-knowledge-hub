"""Ticket workflows, watchers, notifications and escalation (asset-model-revision
§19 item 3)."""
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SessionLocal
from app.main import app
from app.models.issue import Issue, IssueHistory
from app.models.role import Role, RoleBinding
from app.models.schema import Schema
from app.models.user import User
from app.models.workflow import Notification, TicketEscalation, Workflow
from app.models.workspace import Workspace
from app.services import notify, workflows
from tests.test_ledger_transition import token

client = TestClient(app)

FAULT_FLOW = {
    "name": "Fault handling",
    "initial": "open",
    "states": [
        {"key": "open", "name": "Open", "category": "open"},
        {"key": "triage", "name": "Triage", "category": "waiting", "sla_hours": 4, "escalate_to": "lead@lnf.example"},
        {"key": "in_progress", "name": "In Progress", "category": "active"},
        {"key": "resolved", "name": "Resolved", "category": "done"},
        {"key": "closed", "name": "Closed", "category": "done"},
    ],
    "transitions": [
        {"from": "open", "to": "triage", "name": "Triage"},
        {"from": "triage", "to": "in_progress", "name": "Start work", "requires": ["assignee"]},
        {"from": "in_progress", "to": "resolved", "name": "Resolve", "requires": ["resolution"]},
        {"from": "resolved", "to": "in_progress", "name": "Reopen", "requires": ["comment"]},
        {"from": "resolved", "to": "closed", "name": "Close"},
    ],
}


class World:
    def __init__(self):
        self.ws = f"wf-{secrets.token_hex(3)}"
        db = SessionLocal()
        db.add(Workspace(id=self.ws, name="Workflows"))
        db.flush()
        self.fault = Schema(uid=f"{self.ws}:fault", workspace_id=self.ws, name="Fault", applies_to="tickets")
        self.bug = Schema(uid=f"{self.ws}:bug", workspace_id=self.ws, name="Bug", applies_to="tickets")
        db.add_all([self.fault, self.bug])
        self.alice = User(id=f"alice-{self.ws}", email=f"alice@{self.ws}.example", name="Alice")
        self.bob = User(id=f"bob-{self.ws}", email=f"bob@{self.ws}.example", name="Bob")
        db.add_all([self.alice, self.bob])
        db.flush()
        role = Role(id=f"{self.ws}-safety", name="Safety investigator",
                    permissions={"tickets": ["read"], "restricted": ["safety_investigation"]})
        db.add(role)
        db.flush()
        db.add(RoleBinding(workspace_id=self.ws, subject_type="user", subject_id=self.alice.id, role_id=role.id,
                           created_at=datetime.now(timezone.utc)))
        wf = workflows.save(db, self.ws, FAULT_FLOW)
        workflows.bind(db, self.ws, self.fault.uid, wf.uid)
        self.workflow_uid = wf.uid
        self.headers = token(db, self.ws)
        db.commit()
        # Plain values: the session closes, and detached rows cannot be read.
        self.alice_email, self.bob_email, self.bug_uid = self.alice.email, self.bob.email, self.bug.uid
        db.close()

    def create(self, **kw):
        body = {"uid": str(uuid.uuid4()), "title": "Beam lost at the gun", "schema_uid": f"{self.ws}:fault",
                "created_by": "reporter@lnf.example", **kw}
        resp = client.post("/v1/issues", headers=self.headers, json=body)
        assert resp.status_code == 201, resp.text
        return resp.json()

    def move(self, uid, to, **kw):
        return client.post(f"/v1/issues/{uid}/transition", headers=self.headers, json={"to": to, **kw})

    def inbox(self, who):
        return client.get("/v1/notifications", headers=self.headers, params={"recipient": who}).json()


@pytest.fixture()
def w():
    return World()


def test_a_ticket_follows_its_types_workflow_and_its_requirements(w):
    t = w.create()
    assert t["state"] == "open"                        # the workflow's initial state, not "new"
    moves = client.get(f"/v1/issues/{t['uid']}/transitions", headers=w.headers).json()
    assert [m["to"] for m in moves["transitions"]] == ["triage"]
    assert client.put(f"/v1/issues/{t['uid']}", headers=w.headers, json={"state": "in_progress"}).status_code == 409

    assert w.move(t["uid"], "triage").status_code == 200
    refused = w.move(t["uid"], "in_progress")
    assert refused.status_code == 409 and "assignee" in refused.json()["detail"]["error"]
    assert w.move(t["uid"], "in_progress", assignee="tech@lnf.example").status_code == 200
    assert w.move(t["uid"], "resolved").status_code == 409                    # needs a resolution
    done = w.move(t["uid"], "resolved", resolution="Fixed")
    assert done.status_code == 200 and done.json()["closed_at"] is not None
    assert w.move(t["uid"], "in_progress").status_code == 409                 # reopening needs a comment
    assert w.move(t["uid"], "in_progress", comment="the fault came back").json()["closed_at"] is None
    w.move(t["uid"], "resolved", resolution="Fixed")
    closed = client.post(f"/v1/issues/{t['uid']}/close", headers=w.headers)
    assert closed.status_code == 200 and closed.json()["state"] == "closed"

    db = SessionLocal()
    moves = [(h.from_value, h.to_value) for h in db.scalars(select(IssueHistory).where(
        IssueHistory.issue_uid == t["uid"], IssueHistory.field == "Status").order_by(IssueHistory.timestamp))]
    assert moves[:3] == [("open", "triage"), ("triage", "in_progress"), ("in_progress", "resolved")]
    db.close()


def test_the_builtin_workflow_keeps_existing_tickets_unchanged(w):
    t = client.post("/v1/issues", headers=w.headers, json={"uid": str(uuid.uuid4()), "title": "Untyped"}).json()
    assert t["state"] == "new"
    for state in ("pending", "resolved", "new", "closed"):
        assert client.put(f"/v1/issues/{t['uid']}", headers=w.headers, json={"state": state}).status_code == 200
    assert client.post(f"/v1/issues/{t['uid']}/reopen", headers=w.headers).json()["state"] == "new"


def test_watchers_and_notifications_follow_the_ticket(w):
    t = w.create()
    watchers = client.get(f"/v1/issues/{t['uid']}/watchers", headers=w.headers).json()
    assert watchers == ["reporter@lnf.example"]
    w.move(t["uid"], "triage")
    w.move(t["uid"], "in_progress", assignee="tech@lnf.example")
    assert set(client.get(f"/v1/issues/{t['uid']}/watchers", headers=w.headers).json()) == \
        {"reporter@lnf.example", "tech@lnf.example"}
    assert [n["kind"] for n in w.inbox("tech@lnf.example")][-1] == "assigned"
    assert any(n["kind"] == "transitioned" for n in w.inbox("reporter@lnf.example"))

    client.post(f"/v1/issues/{t['uid']}/comments", headers=w.headers, json={
        "uid": str(uuid.uuid4()), "author": "tech@lnf.example", "body": f"@{w.bob_email} can you check the PSU?"})
    bob = w.inbox(w.bob_email)
    assert [n["kind"] for n in bob] == ["mentioned"]
    assert w.bob_email in client.get(f"/v1/issues/{t['uid']}/watchers", headers=w.headers).json()
    # The author of the comment is not told about their own comment.
    assert not any(n["kind"] == "commented" for n in w.inbox("tech@lnf.example"))
    assert client.post("/v1/notifications/read-all", headers=w.headers, params={"recipient": w.bob_email}).json()["ok"]
    assert client.get("/v1/notifications", headers=w.headers,
                      params={"recipient": w.bob_email, "unread": True}).json() == []


def test_a_restricted_ticket_notifies_only_those_who_may_read_it(w):
    t = w.create(attributes={"classification": "restricted:safety_investigation"})
    db = SessionLocal()
    issue = db.get(Issue, t["uid"])
    for who in (w.alice_email, w.bob_email):
        notify.watch(db, issue, who)
    moved = workflows.transition(db, issue, "triage", "investigator")
    notify.on_transition(db, issue, "investigator", moved["from"], moved["to"])
    db.commit()
    recipients = {n.recipient for n in db.scalars(select(Notification).where(Notification.issue_uid == t["uid"]))}
    # Alice holds the safety-investigation grant through her role; Bob does not.
    assert w.alice_email in recipients and w.bob_email not in recipients
    db.close()


def test_a_ticket_that_outstays_its_state_is_escalated_once_per_stay(w):
    t = w.create()
    w.move(t["uid"], "triage")
    db = SessionLocal()
    issue = db.get(Issue, t["uid"])
    later = datetime.now(timezone.utc) + timedelta(hours=5)
    assert notify.escalate_overdue(db, at=later, workspace_id=w.ws) == 1
    assert notify.escalate_overdue(db, at=later + timedelta(hours=1), workspace_id=w.ws) == 0
    db.commit()
    [esc] = db.scalars(select(TicketEscalation).where(TicketEscalation.issue_uid == issue.uid))
    assert esc.state == "triage" and "lead@lnf.example" in esc.escalated_to
    assert [n["kind"] for n in w.inbox("lead@lnf.example")] == ["escalated"]
    db.close()


JIRA = {
    "name": "SPARC Bug workflow",
    "statuses": [{"name": "Open", "statusCategory": {"key": "new"}},
                 {"name": "In Progress", "statusCategory": {"key": "indeterminate"}},
                 {"name": "Done", "statusCategory": {"key": "done"}}],
    "transitions": [{"name": "Start", "from": ["Open"], "to": "In Progress"},
                    {"name": "Finish", "from": ["In Progress"], "to": "Done"},
                    {"name": "Reopen", "from": [], "to": "Open"}],
}


def test_a_jira_workflow_is_imported_and_rehearsed_against_the_migrated_history(w):
    resp = client.post("/v1/workflows/import-jira", headers=w.headers, json={"definition": JIRA})
    assert resp.status_code == 201, resp.text
    wf = resp.json()
    assert [s["category"] for s in wf["states"]] == ["open", "active", "done"]
    assert client.post(f"/v1/workflows/{wf['uid']}/bind", headers=w.headers,
                       json={"schema_uid": w.bug_uid}).status_code == 200

    db = SessionLocal()
    stamp = datetime(2026, 5, 1, tzinfo=timezone.utc)

    def migrated(key, moves, status):
        issue = Issue(uid=str(uuid.uuid4()), workspace_id=w.ws, schema_uid=w.bug_uid, title=key,
                      attributes={"argus_source": "jira", "argus_source_key": key, "argus_source_status": status})
        db.add(issue)
        db.flush()
        for i, (a, b) in enumerate(moves):
            db.add(IssueHistory(uid=str(uuid.uuid4()), issue_uid=issue.uid, type="updated", author="jira",
                                field="status", from_value=a, to_value=b, timestamp=stamp + timedelta(hours=i),
                                backend_id=f"{key}-{i}"))
    migrated("SPARC-1", [("Open", "In Progress"), ("In Progress", "Done"), ("Done", "Open")], "Open")
    db.commit()
    clean = client.get(f"/v1/workflows/{wf['uid']}/rehearsal", headers=w.headers).json()
    assert clean["ok"] and clean["transitions_checked"] == 3

    migrated("SPARC-2", [("Open", "Done"), ("Done", "Waiting for vendor")], "Waiting for vendor")
    db.commit()
    report = client.get(f"/v1/workflows/{wf['uid']}/rehearsal", headers=w.headers).json()
    assert not report["ok"]
    assert report["disallowed"] == [{"from": "open", "to": "done", "count": 1, "example": "SPARC-2"}]
    assert report["unmapped_statuses"] == {"Waiting for vendor": 2}
    db.close()


def test_an_invalid_workflow_is_refused(w):
    bad = {**FAULT_FLOW, "initial": "nowhere",
           "transitions": [{"from": "open", "to": "limbo", "requires": ["blessing"]}]}
    resp = client.post("/v1/workflows", headers=w.headers, json=bad)
    assert resp.status_code == 422
    error = resp.json()["detail"]["error"]
    assert "initial" in error and "limbo" in error and "blessing" in error
