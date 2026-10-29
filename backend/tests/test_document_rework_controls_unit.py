"""Document workflow checks that need no running database or AI service."""
import asyncio
import io
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.routers import documents, intake
from app.schemas.document import DocumentCreate


def test_creation_accepts_an_explicit_global_choice():
    body = DocumentCreate(uid="doc", title="Shared procedure", is_global=True)
    assert body.is_global is True


def test_new_document_persists_the_global_choice_without_a_global_workspace(monkeypatch):
    class Db:
        def get(self, model, uid):
            return SimpleNamespace(is_global=False) if model is documents.Workspace else None

        def scalar(self, *_):
            return None

        def add(self, *_):
            pass

        def flush(self):
            pass

    monkeypatch.setattr(documents, "_validate_revision_attributes", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(documents, "stamp_current_user_attributes", lambda *_: None)
    monkeypatch.setattr(documents, "_actor_user_id", lambda identity: identity)
    monkeypatch.setattr(documents.notify, "follow", lambda *_: None)
    monkeypatch.setattr(documents.notify, "announce", lambda *_: None)
    doc, revision = documents.new_document(
        Db(), DocumentCreate(uid="shared", code="SH-1", title="Shared procedure", is_global=True), "ws", "author")
    assert doc.is_global is True
    assert revision.state == "draft"

    with pytest.raises(HTTPException) as denied:
        documents.new_document(Db(), DocumentCreate(uid="secret", code="SEC-1", title="Secret",
                                                    confidentiality="riservato", is_global=True), "ws", "author")
    assert denied.value.status_code == 422


def test_author_can_withdraw_a_pending_review(monkeypatch):
    revision = SimpleNamespace(uid="rev", state="in_review", authored_by="author", revision_number=2,
                               submitted_at="earlier", review_comment=None)
    document = SimpleNamespace(uid="doc")
    db = SimpleNamespace(commit=lambda: None, refresh=lambda row: None)
    monkeypatch.setattr(documents, "_get_owned_document", lambda *_: document)
    monkeypatch.setattr(documents, "_get_revision", lambda *_: revision)
    monkeypatch.setattr(documents, "_actor_user_id", lambda identity: identity)
    monkeypatch.setattr(documents.notify, "document_changed", lambda *_: None)

    with pytest.raises(HTTPException) as denied:
        documents.withdraw_revision("doc", "rev", "ws", db, "someone-else")
    assert denied.value.status_code == 403
    assert revision.state == "in_review"

    result = documents.withdraw_revision("doc", "rev", "ws", db, "author")
    assert result.state == "draft"
    assert result.submitted_at is None


def test_image_source_uses_vision_and_respects_confidentiality(monkeypatch):
    monkeypatch.setattr(intake, "_allowed", lambda *_: "ws")
    monkeypatch.setattr(intake, "_usable_config", lambda *_: SimpleNamespace(vision_model="vision", allow_confidential=False))
    monkeypatch.setattr(intake, "endpoint_for", lambda config: config)
    monkeypatch.setattr(intake, "look", lambda *args: "# Visible title\n\n- First item")

    def file():
        return UploadFile(file=io.BytesIO(b"image bytes"), filename="minutes.png",
                          headers=Headers({"content-type": "image/png"}))

    result = asyncio.run(intake.extract_text(file(), "interno", None, object(), object(), "ws"))
    assert result["format"] == "image"
    assert "Visible title" in result["text"]
    with pytest.raises(HTTPException) as denied:
        asyncio.run(intake.extract_text(file(), "riservato", None, object(), object(), "ws"))
    assert denied.value.status_code == 409


def test_files_cannot_change_after_a_draft_is_submitted(monkeypatch):
    monkeypatch.setattr(documents, "_get_owned_document", lambda *_: SimpleNamespace(uid="doc"))
    monkeypatch.setattr(documents, "_check_confidentiality", lambda *_: None)
    monkeypatch.setattr(documents, "_get_revision", lambda *_: SimpleNamespace(state="in_review"))
    file = UploadFile(file=io.BytesIO(b"file"), filename="evidence.pdf")
    with pytest.raises(HTTPException) as denied:
        asyncio.run(documents.upload_revision_attachment("doc", "rev", file, "ws", object(), object()))
    assert denied.value.status_code == 409
