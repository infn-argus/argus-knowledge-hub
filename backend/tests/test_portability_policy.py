"""The portability policy (docs/export-import-design.md §20): the trusted initial policy, the strict
one, and the document readers enabled only because these fixtures test them.

The rest of the portability suite runs under the strict policy; here the trusted one is exercised and
compared with it. Neither changes the archive: the same archive verifies and imports under both.
"""
import email.message
import io
import tarfile
import time
import zipfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.portability import PortabilityEvent, PortabilityExport, PortabilityImport, PortabilityJob
from app.portability import blob_scan, jobs, service
from app.portability import policy as policy_mod
from app.portability.policy import Policy
from tests.test_portability import _attach, dbs, env, populate, run_export, run_import  # noqa: F401 — fixtures

SECRET = "api_key = Zk3Qw9Lm2Xp7Rt5Vy8Bn4Jh6"


# =========================================================================== readers with tested fixtures

def _pdf(text: str) -> bytes:
    """A minimal, valid one-page PDF whose page draws `text`."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for i, o in enumerate(objs, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref))
    return out.getvalue()


def _office(kind: str, text: str) -> bytes:
    part = {"docx": ("word/document.xml", f"<w:document><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>"
                                          "</w:document>"),
            "xlsx": ("xl/sharedStrings.xml", f"<sst><si><t>{text}</t></si></sst>")}[kind]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(*part)
    return buf.getvalue()


def _eml(text: str) -> bytes:
    m = email.message.EmailMessage()
    m["From"], m["To"], m["Subject"] = "ops@example.org", "eng@example.org", "settings"
    m.set_content("see attached")
    m.add_attachment(text.encode(), maintype="text", subtype="plain", filename="settings.txt")
    return bytes(m)


def _zip(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("conf/app.ini", text)
    return buf.getvalue()


def _tar(text: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        data = text.encode()
        info = tarfile.TarInfo("conf/app.ini")
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


FIXTURES = {
    "text": (lambda t: t.encode(), "text/plain", "a.txt"),
    "pdf": (_pdf, "application/pdf", "a.pdf"),
    "docx": (lambda t: _office("docx", t), "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "a.docx"),
    "xlsx": (lambda t: _office("xlsx", t), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
             "a.xlsx"),
    "eml": (_eml, "message/rfc822", "a.eml"),
    "zip": (_zip, "application/zip", "a.zip"),
    "tar": (_tar, "application/x-tar", "a.tar.gz"),
}
READER = {"text": "text", "pdf": "pdf", "docx": "office", "xlsx": "office", "eml": "email", "zip": "archive",
          "tar": "archive"}


@pytest.mark.parametrize("fmt", sorted(FIXTURES))
def test_every_enabled_reader_finds_a_planted_secret_and_a_classification_marker(fmt):
    make, mime, name = FIXTURES[fmt]
    assert READER[fmt] in policy_mod.TESTED_READERS
    r = blob_scan.scan("d" * 64, make(SECRET), mime, name, "attachments.x", readers=policy_mod.TESTED_READERS)
    assert r.status == "finding" and any(f["category"] == "secret" for f in r.findings), (r.status, r.findings,
                                                                                             r.reason)
    r = blob_scan.scan("d" * 64, make("STRICTLY CONFIDENTIAL draft"), mime, name, "attachments.x")
    assert any(f["category"] == "classification" for f in r.findings), (fmt, r.status, r.findings)
    r = blob_scan.scan("d" * 64, make("pump P-101 maintenance notes"), mime, name, "attachments.x")
    assert r.status == "ok", (fmt, r.status, r.findings, r.reason)


@pytest.mark.parametrize("fmt", ["pdf", "docx", "eml", "zip"])
def test_a_reader_not_enabled_keeps_the_file_as_opaque_with_a_warning_never_parsed(fmt):
    make, mime, name = FIXTURES[fmt]
    readers = tuple(r for r in policy_mod.TESTED_READERS if r != READER[fmt])
    r = blob_scan.scan("d" * 64, make(SECRET), mime, name, "attachments.x", readers=readers)
    assert r.status == "opaque" and "not enabled" in r.reason


# =========================================================================== the policy itself

def test_trusted_is_the_default_and_every_relaxation_is_named():
    p = policy_mod.from_env({})
    assert p.profile == "trusted" and p == Policy.trusted()
    rel = p.relaxations()
    for name in ("separation_of_duties=False", "step_up=session_confirmation", "full_identity_high_risk=False",
                 "opaque_blobs=allow_with_warning", "export_permission=read", "import_permission=workspace_admin",
                 "evidence_workspace_admins=True"):
        assert name in rel
    assert Policy.strict().relaxations() == []
    d = p.describe()
    assert d["restricted_requires_encryption"] and d["secrets_never_exported"] and d["relaxations"] == rel


def test_any_setting_can_be_made_stricter_by_configuration():
    p = policy_mod.from_env({"ARGUS_PORTABILITY_POLICY_SEPARATION_OF_DUTIES": "1",
                             "ARGUS_PORTABILITY_POLICY_OPAQUE_BLOBS": "require_decision",
                             "ARGUS_PORTABILITY_POLICY_BLOB_READERS": "text,pdf,bogus",
                             "ARGUS_PORTABILITY_POLICY_RETENTION_DAYS": "30"})
    assert p.separation_of_duties and p.opaque_blobs == "require_decision" and p.blob_readers == ("text", "pdf")
    assert p.retention_days == 30 and "separation_of_duties=False" not in p.relaxations()
    assert policy_mod.from_env({"ARGUS_PORTABILITY_POLICY": "strict"}) == Policy.strict()
    with pytest.raises(ValueError):
        policy_mod.from_env({"ARGUS_PORTABILITY_POLICY": "lenient"})
    q = policy_mod.from_env({"ARGUS_PORTABILITY_POLICY_QUERY_TOKENS": "1"})
    assert not q.query_tokens_allowed()           # not without the operator's proxy-redaction confirmation
    assert policy_mod.from_env({"ARGUS_PORTABILITY_POLICY_QUERY_TOKENS": "1",
                                "ARGUS_PORTABILITY_POLICY_PROXY_REDACTS_TOKENS": "1"}).query_tokens_allowed()


def test_step_up_prefers_auth_time_and_otherwise_needs_a_recent_session_and_a_confirmation(tmp_path):
    trusted = service.Config(root=tmp_path, attachments_dir=tmp_path, policy=Policy.trusted())
    strict = service.Config(root=tmp_path, attachments_dir=tmp_path, policy=Policy.strict())
    now = time.time()
    assert service.step_up({"auth_time": now - 10}, strict) == (True, "auth_time")
    assert not service.step_up({"auth_time": now - 3600}, trusted)[0]          # auth_time is never overridden
    assert not service.step_up({"iat": now - 60}, strict)[0]                    # strict: auth_time only
    assert not service.step_up({"iat": now - 60}, trusted)[0]                   # no confirmation
    assert service.step_up({"iat": now - 60}, trusted, confirmed=True) == (True, "recent session + confirmation")
    assert not service.step_up({"iat": now - 7200}, trusted, confirmed=True)[0]  # session too old


# =========================================================================== trusted policy, end to end

@pytest.fixture()
def trusted(env):
    """The same keys and repositories, under the trusted policy."""
    return SimpleNamespace(**{**env.__dict__, "cfg": lambda name, decrypt=True: replace(env.cfg(name, decrypt),
                                                                                        policy=Policy.trusted())})


def test_trusted_opaque_files_travel_labelled_uninspected_and_need_an_accepted_warning_to_import(dbs, trusted, env):
    src, dst = dbs(), dbs()
    s = populate(src, trusted.tmp)
    png = _attach(src, s, "scan.png", b"\x89PNG\r\n\x1a\n" + bytes(range(64)), "image/png", trusted.tmp)
    view, manifest = run_export(src, trusted, s, decisions={"opaque_blobs": None}, identity_profile="full_identity")
    # no decision was taken: the policy let the file through, and the archive says so
    assert view["labels"]["uninspected_content"]
    assert manifest["policy"]["profile"] == "trusted" and "opaque_blobs=allow_with_warning" in \
        manifest["policy"]["relaxations"]
    un = {u["sha256"]: u for u in manifest["blobs"]["uninspected"]}
    assert un[png]["status"] == "opaque" and un[png]["by"] == "policy"
    assert manifest["blobs"]["inspection"]["uninspected"] >= 1
    # the importer sees the warning and must accept it
    cfg = trusted.cfg("dst")
    with Session(dst) as db:
        imp = service.create_import(db, "carol", mode="clone", source={"repository": "escrow", "ref": view["git"]["tag"]},
                                    decisions={}, cfg=cfg)
        service.fetch_git(db, imp, "carol", cfg)
        service.verify_import(db, imp, "carol", cfg)
        service.dry_run(db, imp, "carol", cfg)
        assert imp.dry_run["uninspected_content"]["count"] >= 1
        with pytest.raises(service.ServiceError) as e:
            service.approve_import(db, imp, "carol", cfg=cfg)
        assert e.value.code == "acknowledgement_required"
        service.approve_import(db, imp, "carol", acknowledge_uninspected=True, cfg=cfg)   # one person suffices
        ev = db.scalars(select(PortabilityEvent).where(PortabilityEvent.subject_id == imp.id,
                                                       PortabilityEvent.kind == "approve")).one()
        assert ev.detail["accepted_uninspected"] >= 1 and ev.detail["self_approved"]
        assert ev.detail["policy"] == "trusted" and "separation_of_duties=False" in ev.detail["relaxations"]
        db.commit()
    # the same archive under the strict policy: verified identically, held for the same acknowledgement
    _, report = run_import(dst, env, view["git"]["tag"], root="dst2", finalize=False, expect_ready=False)
    assert report["uninspected_content"]["count"] >= 1


def test_trusted_one_administrator_approves_and_full_identity_for_backup_is_not_high_risk(dbs, trusted, env):
    src = dbs()
    s = populate(src, trusted.tmp)
    cfg = trusted.cfg("src")
    with Session(src) as db:
        exp = service.create_export(db, "alice", mode="workspace", workspaces=[s.ws, s.inv], classifications=[],
                                    destination={"repository": "escrow", "artifact_store": "vault"},
                                    decisions={"opaque_blobs": "approve_opaque"}, purpose="backup", cfg=cfg)
        assert exp.decisions["identity_profile"] == "full_identity" and exp.risk == "normal"
        service.analyse_export(db, exp, "alice", cfg)
        service.approve_export(db, exp, "alice", admin=True, cfg=cfg)            # the requester, alone
        ev = db.scalars(select(PortabilityEvent).where(PortabilityEvent.subject_id == exp.id,
                                                       PortabilityEvent.kind == "approve")).one()
        assert ev.detail["self_approved"] and ev.detail["policy"] == "trusted"
        # the same request under the strict policy is high-risk and needs a second person with step-up
        strict = env.cfg("src")
        exp2 = service.create_export(db, "alice", mode="workspace", workspaces=[s.ws, s.inv], classifications=[],
                                     destination={"repository": "escrow", "artifact_store": "vault"},
                                     decisions={"opaque_blobs": "approve_opaque"}, purpose="backup", cfg=strict)
        assert exp2.risk == "high"
        service.analyse_export(db, exp2, "alice", strict)
        with pytest.raises(service.ServiceError) as e:
            service.approve_export(db, exp2, "alice", admin=True, fresh_auth=True, cfg=strict)
        assert e.value.code == "separation"
        # analytical purpose → pseudonymized
        exp3 = service.create_export(db, "alice", mode="workspace", workspaces=[s.ws], classifications=[],
                                     destination={"repository": "escrow", "artifact_store": "vault"},
                                     purpose="analysis", cfg=cfg)
        assert exp3.decisions["identity_profile"] == "pseudonymized"
        with pytest.raises(service.ServiceError):
            service.create_export(db, "alice", mode="workspace", workspaces=[s.ws], classifications=[],
                                  destination={"repository": "escrow", "artifact_store": "vault"},
                                  purpose="fun", cfg=cfg)
        db.rollback()


def test_a_restricted_export_needs_an_administrator_chosen_approved_recipient(dbs, trusted):
    src = dbs()
    s = populate(src, trusted.tmp)
    cfg = trusted.cfg("src")
    with Session(src) as db:
        for recipients, code in (([], "recipient_required"), (["someone-else"], "invalid")):
            with pytest.raises(service.ServiceError) as e:
                service.create_export(db, "alice", mode="workspace", workspaces=[s.ws], classifications=["costs"],
                                      destination={"repository": "escrow-restricted", "artifact_store": "vault",
                                                   "recipients": recipients}, cfg=cfg)
            assert e.value.code == code
        exp = service.create_export(db, "alice", mode="workspace", workspaces=[s.ws], classifications=["costs"],
                                    destination={"repository": "escrow-restricted", "artifact_store": "vault",
                                                 "recipients": ["escrow-officer"]}, cfg=cfg)
        assert exp.risk == "high"         # restricted classes stay high-risk under every policy
        db.rollback()


# =========================================================================== retention, legal hold, jobs

def test_retention_deletes_expired_files_unless_a_legal_hold_suspends_it(dbs, trusted):
    src = dbs()
    s = populate(src, trusted.tmp)
    a, _ = run_export(src, trusted, s, publish=True)
    b, _ = run_export(src, trusted, s, publish=False)
    cfg = trusted.cfg("src")
    with Session(src) as db:
        held = db.get(PortabilityExport, a["id"])
        with pytest.raises(service.ServiceError):
            service.set_legal_hold(db, held, True, "  ", "admin")                 # a hold needs a reason
        service.set_legal_hold(db, held, True, "audit 2026-17", "admin")
        db.commit()
        assert service.cleanup(db, cfg)["exports"] == []                          # nothing is old yet
        later = datetime.now(timezone.utc) + timedelta(days=cfg.policy.retention_days + 1)
        out = service.cleanup(db, cfg, now=later)
        db.commit()
        assert out["exports"] == [b["id"]] and out["held"] >= 1
        gone = db.get(PortabilityExport, b["id"])
        assert gone.purged_at is not None and gone.state == "expired"
        from pathlib import Path
        assert not Path(gone.out_dir).exists() and Path(held.out_dir).exists()
        kinds = {e.kind for e in db.scalars(select(PortabilityEvent).where(PortabilityEvent.subject_id == b["id"]))}
        assert "purged" in kinds                                                  # the record and audit remain
        service.set_legal_hold(db, held, False, "", "admin")
        assert service.cleanup(db, cfg, now=later)["exports"] == [a["id"]]
        db.commit()


def test_jobs_run_in_the_background_record_failures_and_recover_after_a_restart(dbs):
    eng = dbs()
    factory = sessionmaker(bind=eng)
    done = jobs.start(factory, "export", "exp-x", "generate", "alice", lambda db: None, wait=True)
    assert done["state"] == "completed" and done["metrics"]["seconds"] >= 0

    def boom(db):
        raise service.ServiceError("the repository refused the push", "push_refused", 502)
    failed = jobs.start(factory, "export", "exp-x", "publish-git", "alice", boom, wait=True)
    assert failed["state"] == "failed" and failed["error"]["code"] == "push_refused"
    with factory() as db:
        db.add(PortabilityJob(id="job-stale", subject_kind="import", subject_id="imp-y", action="execute",
                              state="running", requested_by="carol"))
        db.commit()
    assert jobs.recover(factory) == 1
    with factory() as db:
        assert jobs.get(db, "job-stale")["error"]["code"] == "interrupted"
        assert [j["action"] for j in jobs.for_subject(db, "exp-x")] == ["publish-git", "generate"]
        assert db.scalar(select(PortabilityImport)) is None


def test_the_restore_drill_picks_the_newest_checkpoint_by_its_number_not_its_spelling():
    from app.portability.__main__ import _checkpoint_of
    tags = ["export/full/2026-10-01@cp9-1a2b3c4d5e6f", "export/full/2026-10-03@cp184-aa11bb22cc33",
            "export/full/2026-10-02@cp27-0f0f0f0f0f0f", "export/full/old-style@ledger-900"]
    assert max(tags, key=_checkpoint_of) == "export/full/2026-10-03@cp184-aa11bb22cc33"
    assert _checkpoint_of("export/full/old-style@ledger-900") == -1
