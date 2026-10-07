"""The written knowledge indexed without anyone pressing the button: after a document is published or
retired, and on each workspace's timer — both settings of the AI endpoint, both the same incremental run."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.db import SessionLocal
from app.models.llm_config import LLMConfig
from app.routers.ai import _save
from app.schemas.ai import LLMConfigIn
from app.services import knowledge_schedule as ks

from tests.test_knowledge_index import world  # noqa: F401 — the fixture: a workspace with text, a fake model


def configure(ws, **kw):
    db = SessionLocal()
    config = db.get(LLMConfig, ws) or LLMConfig(workspace_id=ws, base_url="https://x/v1", model="m")
    config.embedding_model = "fake-64"
    config.enabled = True
    config.last_check_ok = True
    for k, v in kw.items():
        setattr(config, k, v)
    db.merge(config)
    db.commit()
    db.close()


def passages(ws):
    db = SessionLocal()
    try:
        return db.execute(text("SELECT count(*) FROM knowledge_chunks WHERE workspace_id = :w"), {"w": ws}).scalar()
    finally:
        db.close()


def set_last_run(ws, ago):
    db = SessionLocal()
    db.execute(text("""INSERT INTO knowledge_index_runs (workspace_id, state, started_at, finished_at)
                       VALUES (:w, 'done', :t, :t) ON CONFLICT (workspace_id) DO UPDATE SET state = 'done',
                       started_at = :t, finished_at = :t"""),
               {"w": ws, "t": datetime.now(timezone.utc) - ago})
    db.commit()
    db.close()


def due(ws):
    db = SessionLocal()
    try:
        return ws in ks.due(db)
    finally:
        db.close()


def test_a_requested_run_indexes_the_workspace(world):  # noqa: F811
    configure(world["ws"])
    ks.request(world["ws"], wait=True)
    assert passages(world["ws"]) > 0


def test_an_endpoint_not_checked_or_switched_off_is_never_used(world):  # noqa: F811
    configure(world["ws"], last_check_ok=False)
    ks.request(world["ws"], wait=True)
    assert passages(world["ws"]) == 0
    assert not due(world["ws"])


def test_a_publication_triggers_a_run_only_where_the_setting_says_so(world, monkeypatch):  # noqa: F811
    asked = []
    monkeypatch.setattr(ks, "request", lambda ws, *a, **k: asked.append(ws))
    monkeypatch.setenv("ARGUS_KNOWLEDGE_SCHEDULER", "on")
    configure(world["ws"])
    db = SessionLocal()
    ks.after_document_change(db, world["ws"])
    configure(world["ws"], index_on_publish=False)
    ks.after_document_change(db, world["ws"])
    db.close()
    assert asked == [world["ws"]]


def test_the_timer_runs_a_workspace_once_its_interval_has_passed(world):  # noqa: F811
    ws = world["ws"]
    configure(ws)
    assert due(ws), "never indexed: due at once"
    set_last_run(ws, timedelta(hours=1))
    assert not due(ws), "indexed an hour ago, every 12 hours by default"
    set_last_run(ws, timedelta(hours=13))
    assert due(ws)
    configure(ws, index_interval_hours=24)
    assert not due(ws)
    configure(ws, index_interval_hours=0)
    set_last_run(ws, timedelta(days=30))
    assert not due(ws), "0 hours: no timer"


def test_requests_during_a_run_become_one_more_run(world, monkeypatch):  # noqa: F811
    runs = []

    def slow_run(ws, factory):
        runs.append(ws)
        if len(runs) == 1:
            for _ in range(3):
                ks.request(ws)                              # three publications while the first run goes
    monkeypatch.setattr(ks, "_run_once", slow_run)
    ks.request(world["ws"], wait=True)
    assert runs == [world["ws"]] * 2
    assert world["ws"] not in ks._running


def test_settings_left_out_by_a_client_are_kept(world):  # noqa: F811
    ws = world["ws"]
    db = SessionLocal()
    out = _save(db, ws, LLMConfigIn(base_url="https://x/v1", model="m"))
    assert (out.index_on_publish, out.index_interval_hours) == (True, 12)
    out = _save(db, ws, LLMConfigIn(base_url="https://x/v1", model="m", index_on_publish=False, index_interval_hours=6))
    assert (out.index_on_publish, out.index_interval_hours) == (False, 6)
    out = _save(db, ws, LLMConfigIn(base_url="https://x/v1", model="m"))
    assert (out.index_on_publish, out.index_interval_hours) == (False, 6)
    db.close()
    with pytest.raises(ValueError):
        LLMConfigIn(base_url="x", model="m", index_interval_hours=-1)
