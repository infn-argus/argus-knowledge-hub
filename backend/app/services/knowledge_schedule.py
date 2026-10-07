"""Keeping the written knowledge indexed for Ask ARGUS without anyone pressing the button.

Two triggers, each a workspace's AI setting (Administration → AI, beside the endpoint):

- after a document is published or retired (`index_on_publish`): the procedure people just approved is
  what they will ask about next, so the index catches up within moments rather than at the next timer;
- on a timer (`index_interval_hours`, 12 by default, 0 for none): everything else with text — tickets and
  their comments, comments on equipment, attached files, what an import brought in — changes too often
  and from too many places to follow one by one.

Either way it is the same incremental run as the button's (knowledge_index.index_workspace): sources
whose text has not changed are skipped, so a run after one publication embeds that one document.

One run per workspace at a time. Within this process, a trigger that arrives while a run is going is
remembered and runs once more after it (ten publications in a row are two runs, not ten). Across
processes, a Postgres advisory lock decides: a replica that cannot take it leaves the work to the one
that has. A run left "running" by the index button is not interrupted.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_HOURS = 12
# How often the timer looks for a workspace that is due. A run is due by the hour, so minutes do not matter.
TICK_SECONDS = 300
# A run still "running" after this long died with its process: it no longer holds anything back.
STALE_RUN = timedelta(hours=6)

_lock = threading.Lock()
_running: set[str] = set()
_again: set[str] = set()
_scheduler: Optional[threading.Thread] = None


def enabled() -> bool:
    """ARGUS_KNOWLEDGE_SCHEDULER=off turns both triggers off for this process (the tests, a one-off command)."""
    return os.environ.get("ARGUS_KNOWLEDGE_SCHEDULER", "on").lower() not in ("off", "0", "false", "no")


def _usable(config) -> bool:
    return bool(config is not None and config.enabled and config.last_check_ok and config.embedding_model)


def interval_hours(config) -> int:
    value = getattr(config, "index_interval_hours", None)
    return DEFAULT_INTERVAL_HOURS if value is None else max(0, int(value))


def on_publish(config) -> bool:
    return getattr(config, "index_on_publish", None) is not False


def _aware(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _last(run: dict) -> Optional[datetime]:
    return _aware(run.get("finished_at")) or _aware(run.get("started_at"))


def schedule(config, run: Optional[dict]) -> dict:
    """What the settings page shows: whether indexing follows publication, the timer, and the next timed run."""
    hours = interval_hours(config) if config is not None else DEFAULT_INTERVAL_HOURS
    out = {"on_publish": on_publish(config) if config is not None else True, "interval_hours": hours,
           "active": _usable(config), "next_at": None}
    if out["active"] and hours:
        last = _last(run or {})
        out["next_at"] = (last + timedelta(hours=hours)) if last else datetime.now(timezone.utc)
    return out


# --------------------------------------------------------------------------- a run

def _factory() -> Callable[[], Session]:
    from app.db import SessionLocal
    return SessionLocal


def _run_once(workspace_id: str, factory: Callable[[], Session]) -> Optional[dict]:
    from app.routers.ai import endpoint_for
    from app.services import knowledge_index
    from app.services.ai_config import resolve
    from app.services.llm import LLMError

    db = factory()
    lock = None
    key = f"knowledge-index:{workspace_id}"
    try:
        config, _from = resolve(db, workspace_id)
        if not _usable(config):
            return None
        # Its own connection: a Session hands its connection back to the pool at every commit, and an
        # advisory lock belongs to the connection that took it.
        lock = db.get_bind().connect()
        if not lock.execute(text("SELECT pg_try_advisory_lock(hashtext(:k))"), {"k": key}).scalar():
            lock.close()
            lock = None
            return None
        if knowledge_index.store_ready(db):
            run = db.execute(text("SELECT state, started_at FROM knowledge_index_runs WHERE workspace_id = :w"),
                             {"w": workspace_id}).mappings().first()
            started = _aware(run["started_at"]) if run else None
            if run and run["state"] == "running" and started and datetime.now(timezone.utc) - started < STALE_RUN:
                return None                                 # the index button's run is going
        try:
            return knowledge_index.index_workspace(db, workspace_id, endpoint_for(config))
        except LLMError as e:
            db.rollback()
            if knowledge_index.store_ready(db):
                db.execute(text("""INSERT INTO knowledge_index_runs (workspace_id, state, started_at, finished_at, result)
                                   VALUES (:w, 'failed', now(), now(), CAST(:r AS jsonb))
                                   ON CONFLICT (workspace_id) DO UPDATE SET state = 'failed', finished_at = now(),
                                   result = EXCLUDED.result"""),
                           {"w": workspace_id, "r": json.dumps({"failed": [str(e)]})})
                db.commit()
            log.warning("indexing %s failed: %s", workspace_id, e)
            return None
    finally:
        if lock is not None:
            lock.execute(text("SELECT pg_advisory_unlock(hashtext(:k))"), {"k": key})
            lock.close()
        db.close()


def _worker(workspace_id: str, factory: Callable[[], Session]) -> None:
    try:
        while True:
            try:
                _run_once(workspace_id, factory)
            except Exception:  # noqa: BLE001 — one workspace's failure must not end the next request for it
                log.exception("indexing %s failed", workspace_id)
            with _lock:
                if workspace_id not in _again:
                    _running.discard(workspace_id)
                    return
                _again.discard(workspace_id)
    except BaseException:
        with _lock:
            _running.discard(workspace_id)
            _again.discard(workspace_id)
        raise


def request(workspace_id: str, factory: Optional[Callable[[], Session]] = None, wait: bool = False) -> None:
    """Bring the workspace's index up to date in the background (or, with `wait`, before returning)."""
    factory = factory or _factory()
    with _lock:
        if workspace_id in _running:
            _again.add(workspace_id)
            return
        _running.add(workspace_id)
    if wait:
        _worker(workspace_id, factory)
    else:
        threading.Thread(target=_worker, args=(workspace_id, factory), daemon=True,
                         name=f"knowledge-index-{workspace_id}").start()


def after_document_change(db: Session, workspace_id: str) -> None:
    """A document was published or retired: catch the index up, when this workspace's settings say so."""
    from app.services.ai_config import resolve
    try:
        config, _from = resolve(db, workspace_id)
    except Exception:  # noqa: BLE001 — indexing is a convenience; the publication has already happened
        log.warning("indexing after a document change skipped", exc_info=True)
        return
    if enabled() and _usable(config) and on_publish(config):
        request(workspace_id)


# --------------------------------------------------------------------------- the timer

def due(db: Session, now: Optional[datetime] = None) -> list[str]:
    """Workspaces whose last run is older than their interval (or that never ran)."""
    from app.models.workspace import Workspace
    from app.services import knowledge_index
    from app.services.ai_config import resolve
    now = now or datetime.now(timezone.utc)
    if not knowledge_index.pgvector_available(db):
        return []
    last: dict[str, Optional[datetime]] = {}
    if knowledge_index.store_ready(db):
        for w, finished, started in db.execute(text(
                "SELECT workspace_id, finished_at, started_at FROM knowledge_index_runs")):
            last[w] = _aware(finished) or _aware(started)
    out = []
    for workspace_id in db.scalars(select(Workspace.id)):
        config, _from = resolve(db, workspace_id)
        hours = interval_hours(config) if config is not None else 0
        if not _usable(config) or not hours:
            continue
        previous = last.get(workspace_id)
        if previous is None or now - previous >= timedelta(hours=hours):
            out.append(workspace_id)
    return out


def tick(factory: Optional[Callable[[], Session]] = None) -> list[str]:
    factory = factory or _factory()
    db = factory()
    try:
        workspaces = due(db)
    finally:
        db.close()
    for workspace_id in workspaces:
        request(workspace_id, factory)
    return workspaces


def _loop(factory: Callable[[], Session]) -> None:
    while True:
        time.sleep(TICK_SECONDS)
        try:
            started = tick(factory)
            if started:
                log.info("indexing the written knowledge of %s on schedule", ", ".join(started))
        except Exception:  # noqa: BLE001 — a database briefly away must not stop the timer for good
            log.warning("scheduled indexing skipped", exc_info=True)


def start_scheduler() -> None:
    """Starts the timer once per process."""
    global _scheduler
    if not enabled():
        return
    if _scheduler is not None:
        return
    _scheduler = threading.Thread(target=_loop, args=(_factory(),), daemon=True, name="knowledge-schedule")
    _scheduler.start()
