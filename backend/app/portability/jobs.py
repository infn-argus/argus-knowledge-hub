"""Long portability steps as background jobs: queued → running → completed | failed.

Generating, publishing, fetching, verifying, executing and finalizing can take minutes. The web pages
start them as jobs and poll `GET /v1/portability/jobs/{id}`; the API and the CLI can still run them
synchronously. A job runs in a worker thread of the API process with its own database session; the
step it runs is the same service function, audited the same way. A job still `running` when the
process starts again was interrupted: it is marked failed (`interrupted`), and the step can be run
again — every step is idempotent, and an interrupted import resumes from its staging checkpoints.

A running step reports its progress with `report(stage, done, total)`: what it is doing and how far it has got,
shown by the page as a bar (`metrics.progress`). Not provided yet: cancellation, and a separate worker pool.
"""
from __future__ import annotations

import contextvars
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.portability import PortabilityJob

_LOCK = threading.Lock()
_RUNNING: dict[tuple, str] = {}       # (subject_kind, subject_id) -> job id: one job per subject at a time
# The job a step runs in, for its progress reports; none when the step runs synchronously (API, CLI, tests).
_CURRENT: contextvars.ContextVar = contextvars.ContextVar("portability_job", default=None)
_LAST_REPORT: dict[str, float] = {}


def report(stage: str, done: Optional[int] = None, total: Optional[int] = None, force: bool = False) -> None:
    """What the running step is doing, and how far it has got (at most once a second, unless `force`)."""
    current = _CURRENT.get()
    if current is None:
        return
    factory, job_id = current
    t = time.monotonic()
    if not force and t - _LAST_REPORT.get(job_id, 0) < 1.0:
        return
    _LAST_REPORT[job_id] = t
    try:
        with factory() as db:
            job = db.get(PortabilityJob, job_id)
            job.metrics = {**(job.metrics or {}), "progress": {
                "stage": stage, "done": done, "total": total,
                "percent": round(100 * done / total, 1) if done is not None and total else None,
                "at": now().isoformat()}}
            db.commit()
    except Exception:  # noqa: BLE001 — a progress note must never fail the step
        pass


def now() -> datetime:
    return datetime.now(timezone.utc)


def view(job: PortabilityJob) -> dict:
    return {"id": job.id, "subject_kind": job.subject_kind, "subject_id": job.subject_id, "action": job.action,
            "state": job.state, "requested_by": job.requested_by,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "error": job.error, "metrics": job.metrics}


def start(factory: sessionmaker, subject_kind: str, subject_id: str, action: str, actor: str,
          fn: Callable[[Session], object], wait: bool = False) -> dict:
    """Queue `fn(session)` for a subject. A subject runs one job at a time: a second request while one
    runs returns that job instead of starting another."""
    with _LOCK:
        busy = _RUNNING.get((subject_kind, subject_id))
        if busy:
            with factory() as db:
                return view(db.get(PortabilityJob, busy))
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        _RUNNING[(subject_kind, subject_id)] = job_id
    with factory() as db:
        db.add(PortabilityJob(id=job_id, subject_kind=subject_kind, subject_id=subject_id, action=action,
                              state="queued", requested_by=actor))
        db.commit()
    t = threading.Thread(target=_run, args=(factory, job_id, subject_kind, subject_id, fn), daemon=True,
                         name=f"portability-{action}")
    t.start()
    if wait:
        t.join()
    with factory() as db:
        return view(db.get(PortabilityJob, job_id))


def _run(factory: sessionmaker, job_id: str, subject_kind: str, subject_id: str, fn) -> None:
    import resource
    import sys
    started = time.monotonic()
    try:
        with factory() as db:
            job = db.get(PortabilityJob, job_id)
            job.state, job.started_at = "running", now()
            db.commit()
        token = _CURRENT.set((factory, job_id))
        try:
            with factory() as db:
                fn(db)
                db.commit()
        finally:
            _CURRENT.reset(token)
            _LAST_REPORT.pop(job_id, None)
        state, error = "completed", None
    except Exception as e:  # noqa: BLE001 — the job records why
        state = "failed"
        error = {"error": str(e)[:2000], "code": getattr(e, "code", type(e).__name__),
                 **{k: v for k, v in (getattr(e, "detail", None) or {}).items() if k in ("findings", "problems")}}
    finally:
        with _LOCK:
            _RUNNING.pop((subject_kind, subject_id), None)
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    with factory() as db:
        job = db.get(PortabilityJob, job_id)
        job.state, job.finished_at, job.error = state, now(), error
        job.metrics = {"progress": (job.metrics or {}).get("progress"),
                       "seconds": round(time.monotonic() - started, 2),
                       "process_peak_memory_mb": round(peak / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)}
        db.commit()


def recover(factory: sessionmaker) -> int:
    """At start-up: jobs left running by a previous process were interrupted."""
    n = 0
    with factory() as db:
        for job in db.scalars(select(PortabilityJob).where(PortabilityJob.state.in_(("queued", "running")))):
            job.state, job.finished_at = "failed", now()
            job.error = {"error": "interrupted by a restart; run the step again", "code": "interrupted"}
            n += 1
        db.commit()
    return n


def for_subject(db: Session, subject_id: str, limit: int = 20) -> list[dict]:
    return [view(j) for j in db.scalars(select(PortabilityJob).where(PortabilityJob.subject_id == subject_id)
                                        .order_by(PortabilityJob.created_at.desc()).limit(limit))]


def get(db: Session, job_id: str) -> Optional[dict]:
    job = db.get(PortabilityJob, job_id)
    return view(job) if job else None
