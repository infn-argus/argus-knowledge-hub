"""The ledger's own writes (asset-model-revision §13 S5).

In a workspace switched to ledger-only, a database trigger refuses any
change to a record's facts (attributes, type, key, name, status, merge)
and to its relations unless the transaction is marked as the ledger
writing. The ledger's entry points mark it for as long as they run; any
other path — an endpoint, a script, an importer — is refused by the
database itself.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps

from sqlalchemy import event, text
from sqlalchemy.orm import Session

KEY = "ledger_writer"
SETTING = "argus.writer"


def _mark(db: Session, on: bool) -> None:
    db.execute(text("SELECT set_config(:k, :v, true)"), {"k": SETTING, "v": "ledger" if on else ""})


@contextmanager
def writing(db: Session):
    depth = db.info.get(KEY, 0)
    db.info[KEY] = depth + 1
    if depth == 0:
        db.flush()                 # what was pending before is not the ledger's
        _mark(db, True)
    ok = False
    try:
        yield
        ok = True
    finally:
        try:
            if depth == 0 and ok:
                db.flush()         # the ledger's pending writes go out while it is marked
        finally:
            db.info[KEY] = depth
            if depth == 0:
                try:
                    _mark(db, False)
                except Exception:  # an aborted transaction; its rollback clears the mark anyway
                    pass


def ledger_writer(fn):
    """Mark a ledger entry point: its first argument is the session."""
    @wraps(fn)
    def wrapper(db, *args, **kwargs):
        with writing(db):
            return fn(db, *args, **kwargs)
    return wrapper


@event.listens_for(Session, "after_begin")
def _carry_the_mark(session, transaction, connection):
    """A commit inside a ledger operation starts a new transaction; the mark
    (transaction-local) is set again on it."""
    if session.info.get(KEY, 0) > 0:
        connection.execute(text("SELECT set_config(:k, 'ledger', true)"), {"k": SETTING})


# --------------------------------------------------------------------------- the guard

GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION ledger_only_guard() RETURNS trigger AS $$
DECLARE
    ws text;
    is_only boolean;
BEGIN
    IF coalesce(current_setting('argus.writer', true), '') = 'ledger'
       OR coalesce(current_setting('argus.audit_purge', true), '') = 'on' THEN
        RETURN coalesce(NEW, OLD);
    END IF;
    IF TG_OP = 'DELETE' THEN ws := OLD.workspace_id; ELSE ws := NEW.workspace_id; END IF;
    SELECT ledger_only INTO is_only FROM workspaces WHERE id = ws;
    IF NOT coalesce(is_only, false) THEN
        RETURN coalesce(NEW, OLD);
    END IF;
    IF TG_TABLE_NAME = 'assets' AND TG_OP = 'UPDATE'
       AND NEW.attributes IS NOT DISTINCT FROM OLD.attributes AND NEW.type IS NOT DISTINCT FROM OLD.type
       AND NEW.key IS NOT DISTINCT FROM OLD.key AND NEW.name IS NOT DISTINCT FROM OLD.name
       AND NEW.record_status IS NOT DISTINCT FROM OLD.record_status
       AND NEW.merged_into_uid IS NOT DISTINCT FROM OLD.merged_into_uid
       AND NEW.workspace_id IS NOT DISTINCT FROM OLD.workspace_id THEN
        RETURN NEW;                -- display and caching columns: not facts
    END IF;
    RAISE EXCEPTION 'workspace % is ledger-only: % on % must go through the fact ledger', ws, TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'insufficient_privilege', HINT = 'ledger-only';
END;
$$ LANGUAGE plpgsql;
"""
GUARDED = ("assets", "relations")


def guard_sql(table: str) -> str:
    return (f"DROP TRIGGER IF EXISTS {table}_ledger_only ON {table}; "
            f"CREATE TRIGGER {table}_ledger_only BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION ledger_only_guard();")


def install_guard(bind) -> None:
    bind.execute(text(GUARD_FUNCTION))
    for table in GUARDED:
        bind.execute(text(guard_sql(table)))


def _attach_ddl() -> None:
    """Databases built with `create_all` get the guard too."""
    from sqlalchemy import DDL
    from app.db import Base
    for table in GUARDED:
        t = Base.metadata.tables.get(table)
        if t is not None:
            event.listen(t, "after_create", DDL(GUARD_FUNCTION))
            event.listen(t, "after_create", DDL(guard_sql(table)))
