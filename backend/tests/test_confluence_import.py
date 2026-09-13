"""Confluence pages as documents.

The conversion is the part worth testing hard: Confluence stores pages in
its own XHTML dialect, and anything the converter drops silently is
content nobody will notice is missing until they need it.
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
from app.models.document import Document, DocumentRelation, DocumentRevision
from app.models.import_job import ImportJob
from app.models.schema import Schema
from app.models.workspace import Workspace
from app.services.confluence_import import (
    choose_document_type,
    run_confluence_import,
    storage_to_markdown,
)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


def test_headings_lists_and_links_become_markdown():
    markdown = storage_to_markdown(
        "<h1>Vacuum recovery</h1>"
        "<p>Follow <strong>exactly</strong>.</p>"
        "<ol><li>Close the gate valve</li><li>Start the pump</li></ol>"
        '<p>See <a href="https://wiki.invalid/x">the manual</a>.</p>'
    )
    assert "# Vacuum recovery" in markdown
    assert "**exactly**" in markdown
    assert "1. Close the gate valve" in markdown
    assert "[the manual](https://wiki.invalid/x)" in markdown


def test_tables_survive():
    """A procedure's parameters are usually a table; losing it loses the
    part people actually came for."""
    markdown = storage_to_markdown(
        "<table><tbody>"
        "<tr><th>Parameter</th><th>Value</th></tr>"
        "<tr><td>Pressure</td><td>1e-9 mbar</td></tr>"
        "</tbody></table>"
    )
    assert "Parameter" in markdown and "1e-9 mbar" in markdown
    assert "|" in markdown, "should be a markdown table, not flattened prose"


def test_code_macro_keeps_its_content_and_language():
    markdown = storage_to_markdown(
        '<ac:structured-macro ac:name="code">'
        '<ac:parameter ac:name="language">python</ac:parameter>'
        "<ac:plain-text-body><![CDATA[caget BTF:PRESSURE]]></ac:plain-text-body>"
        "</ac:structured-macro>"
    )
    assert "caget BTF:PRESSURE" in markdown
    # The language belongs on the fence — it is what makes the block
    # readable and highlightable downstream.
    assert "```python" in markdown


def test_warning_panel_is_not_silently_dropped():
    """A safety warning that vanishes in conversion is the worst possible
    thing for this converter to do."""
    markdown = storage_to_markdown(
        '<ac:structured-macro ac:name="warning">'
        "<ac:rich-text-body><p>Interlock must be armed.</p></ac:rich-text-body>"
        "</ac:structured-macro>"
    )
    assert "Interlock must be armed." in markdown
    assert ">" in markdown, "a panel should read as a blockquote"


def test_unconvertible_macro_says_so_rather_than_leaving_a_hole():
    markdown = storage_to_markdown(
        '<ac:structured-macro ac:name="jira"><ac:parameter ac:name="key">LNF-1</ac:parameter>'
        "</ac:structured-macro>"
    )
    assert "jira" in markdown.lower()
    assert "original" in markdown.lower()


def test_page_and_attachment_links_keep_their_names():
    markdown = storage_to_markdown(
        '<ac:link><ri:page ri:content-title="Beam interlock" /></ac:link>'
        '<ac:link><ri:attachment ri:filename="layout.pdf" /></ac:link>'
    )
    assert "Beam interlock" in markdown
    assert "layout.pdf" in markdown


def test_no_raw_confluence_markup_survives():
    """Whatever isn't understood must not reach the reader as tags."""
    markdown = storage_to_markdown(
        '<p>Before</p><ac:structured-macro ac:name="toc" /><ri:user ri:userkey="abc" />'
        "<p>After</p>"
    )
    assert "ac:" not in markdown and "ri:" not in markdown
    assert "Before" in markdown and "After" in markdown


def test_document_type_comes_from_labels_then_title():
    assert choose_document_type(["procedure"], "Anything") == "Procedure"
    assert choose_document_type(["sicurezza"], "Anything") == "Safety Document"
    assert choose_document_type([], "Runbook: vacuum loss") == "Runbook"
    assert choose_document_type([], "Verbale riunione") == "Meeting Minutes"
    # Unrecognised becomes a Note rather than being forced somewhere wrong.
    assert choose_document_type(["random"], "Something else") == "Note"


PAGES = [
    {
        "id": "101",
        "title": "Vacuum recovery procedure",
        "space": {"key": "LNF"},
        "version": {"number": 3, "when": "2026-09-01T10:00:00.000Z",
                    "by": {"displayName": "Marco Rossi"}},
        "metadata": {"labels": {"results": [{"name": "procedure"}]}},
        "body": {"storage": {"value": "<h1>Recovery</h1><p>Camera LNFT2-145356 first.</p>"}},
    },
    {
        "id": "102",
        "title": "Shift report 2026-09-02",
        "space": {"key": "LNF"},
        "version": {"number": 1, "when": "2026-09-02T18:00:00.000Z",
                    "by": {"displayName": "Giulia Bianchi"}},
        "metadata": {"labels": {"results": [{"name": "logbook"}]}},
        "body": {"storage": {"value": "<p>Quiet shift.</p>"}},
    },
]


class _ConfluenceStub(BaseHTTPRequestHandler):
    pages = PAGES

    def log_message(self, *a):
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
        if parsed.path == "/rest/api/space":
            self._json({"results": [{"key": "LNF"}]})
        elif parsed.path in ("/rest/api/content", "/rest/api/content/search"):
            start = int(parse_qs(parsed.query).get("start", ["0"])[0])
            self._json({
                "results": self.pages[start:start + 50],
                "size": len(self.pages),
                "totalSize": len(self.pages),
            })
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture()
def confluence_stub():
    server = HTTPServer(("127.0.0.1", 0), _ConfluenceStub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _document(db, workspace_id: str, page_id: str) -> Document:
    """Codes are unique across the installation, so a second workspace
    importing the same page gets a qualified one — look the document up by
    workspace rather than assuming the readable code."""
    return db.scalar(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.code.like(f"CONF-LNF-{page_id}%"),
        )
    )


def _run(workspace_id, base_url, **kwargs):
    db = SessionLocal()
    job = ImportJob(uid=str(uuid.uuid4()), workspace_id=workspace_id, source="confluence")
    db.add(job)
    db.commit()
    job_uid = job.uid
    db.close()
    run_confluence_import(job_uid, workspace_id, base_url, "pat", "LNF", None, **kwargs)
    db = SessionLocal()
    job = db.get(ImportJob, job_uid)
    result = (job.status, job.error, dict(job.counts or {}))
    db.close()
    return result


def test_pages_become_typed_documents_with_a_published_revision(confluence_stub):
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"
    # Asset keys are unique across the installation, so the page has to name
    # the one this test creates.
    asset_key = f"LNFT2-{secrets.randbelow(900000) + 100000}"
    pages = json.loads(json.dumps(PAGES))
    pages[0]["body"]["storage"]["value"] = (
        f"<h1>Recovery</h1><p>Camera {asset_key} first.</p>"
    )
    _ConfluenceStub.pages = pages

    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.flush()
    db.add(Schema(uid=f"sc-{suffix}", workspace_id=ws, name="Cameras"))
    db.flush()
    db.add(Asset(uid=f"as-{suffix}", workspace_id=ws, schema_uid=f"sc-{suffix}",
                 key=asset_key, name="FI4-B-CAM-VIS-001", type="Cameras"))
    db.commit()
    db.close()

    status, error, counts = _run(ws, confluence_stub)
    assert status == "succeeded", error
    assert counts["documents"] == 2

    db = SessionLocal()
    procedure = _document(db, ws, "101")
    assert procedure.title == "Vacuum recovery procedure"
    assert procedure.source == "confluence"
    assert procedure.document_type_uid.endswith(":procedure")

    revision = db.get(DocumentRevision, procedure.current_revision_uid)
    # An imported page is already in use at the source; parking it in draft
    # would hide the whole library behind a review nobody asked for.
    assert revision.state == "published"
    assert "# Recovery" in revision.body_markdown
    assert revision.attributes["argus_source_version"] == 3
    assert revision.attributes["argus_source_author"] == "Marco Rossi"
    assert revision.attributes["argus_source_url"].endswith("pageId=101")

    logbook = _document(db, ws, "102")
    assert logbook.document_type_uid.endswith(":logbook-entry")

    # A page naming an object key is linked to that object.
    links = db.scalars(
        select(DocumentRelation).where(DocumentRelation.from_document_uid == procedure.uid)
    ).all()
    assert [(r.to_type, r.to_uid) for r in links] == [("asset", f"as-{suffix}")]
    db.close()


def test_reimporting_an_unchanged_page_adds_no_revision(confluence_stub):
    """The page version is what says whether anything changed; without that
    check a document's history fills with identical revisions."""
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"
    _ConfluenceStub.pages = PAGES

    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.commit()
    db.close()

    _run(ws, confluence_stub)
    status, error, counts = _run(ws, confluence_stub)
    assert status == "succeeded", error
    assert counts["documents_unchanged"] == 2
    assert counts.get("documents", 0) == 0

    db = SessionLocal()
    document = _document(db, ws, "101")
    revisions = db.scalars(
        select(DocumentRevision).where(DocumentRevision.document_uid == document.uid)
    ).all()
    assert len(revisions) == 1
    db.close()


def test_an_edited_page_supersedes_the_previous_revision(confluence_stub):
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"
    _ConfluenceStub.pages = PAGES

    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.commit()
    db.close()
    _run(ws, confluence_stub)

    edited = json.loads(json.dumps(PAGES))
    edited[0]["version"]["number"] = 4
    edited[0]["body"]["storage"]["value"] = "<h1>Recovery</h1><p>Revised.</p>"
    _ConfluenceStub.pages = edited
    status, error, counts = _run(ws, confluence_stub)
    assert status == "succeeded", error
    assert counts["documents_updated"] == 1

    db = SessionLocal()
    document = _document(db, ws, "101")
    revisions = sorted(
        db.scalars(
            select(DocumentRevision).where(DocumentRevision.document_uid == document.uid)
        ).all(),
        key=lambda r: r.revision_number,
    )
    assert [r.revision_number for r in revisions] == [1, 2]
    assert revisions[0].state == "superseded"
    assert revisions[0].superseded_by_uid == revisions[1].uid
    assert revisions[1].state == "published"
    assert "Revised." in revisions[1].body_markdown
    assert document.current_revision_uid == revisions[1].uid
    db.close()
    _ConfluenceStub.pages = PAGES


def test_a_wrong_base_url_names_the_context_path(confluence_stub):
    suffix = secrets.token_hex(4)
    ws = f"ws-{suffix}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name="WS"))
    db.commit()
    db.close()

    status, error, _counts = _run(ws, confluence_stub + "/nope")
    assert status == "failed"
    assert "context path" in (error or "")
