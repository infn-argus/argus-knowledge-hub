"""Import issues from a Jira issue tracker (issues.infn.it) as tickets.

Distinct from jira_import, which reads Insight/Assets *objects*. This
reads the issue tracker: work, not equipment. The two meet where a ticket
names an asset — an Insight object referenced from an issue becomes a
link between the ticket and the object already imported here.
"""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.asset import Asset
from app.models.asset_subresources import AssetTicket
from app.models.import_job import ImportJob
from app.models.issue import Issue, IssueComment
from app.services.import_merge import should_write
from app.services.jira_import import (
    _TimeoutSession,
    _author_display_name,
    _describe_error,
    _parse_jira_dt,
    _record_diagnostic,
    _set_progress,
)

PAGE_SIZE = 100

# Jira lets every project invent its own workflow, so the specific status
# names can't be relied on. Every status does carry a statusCategory, which
# Jira itself constrains to three values — that is the part worth mapping.
_CATEGORY_TO_STATE = {
    "new": "new",
    "undefined": "new",
    "indeterminate": "in_progress",
    "done": "resolved",
}

# Where a status name is unambiguous, it beats the category: "Closed" and
# "Pending" are both meaningful distinctions that the three categories flatten
# away ("done" and "indeterminate" respectively).
_NAME_TO_STATE = {
    "closed": "closed",
    "chiuso": "closed",
    "done": "closed",
    "resolved": "resolved",
    "risolto": "resolved",
    "pending": "pending",
    "in attesa": "pending",
    "waiting": "pending",
    "waiting for customer": "pending",
    "waiting for support": "pending",
    "on hold": "pending",
    "sospeso": "pending",
    "in progress": "in_progress",
    "in corso": "in_progress",
    "open": "new",
    "aperto": "new",
    "to do": "new",
    "new": "new",
    "nuovo": "new",
}

# Jira ships two priority schemes depending on the project template, and
# INFN's tracker may use either.
_PRIORITY_MAP = {
    "blocker": "blocker", "bloccante": "blocker",
    "critical": "critical", "critico": "critical", "highest": "critical",
    "major": "high", "high": "high", "alta": "high", "alto": "high",
    "medium": "medium", "normal": "medium", "media": "medium", "normale": "medium",
    "minor": "low", "low": "low", "bassa": "low", "basso": "low",
    "trivial": "low", "lowest": "low",
}


def map_state(status: dict) -> str:
    """Jira status -> one of our five ticket states."""
    name = (status.get("name") or "").strip().lower()
    if name in _NAME_TO_STATE:
        return _NAME_TO_STATE[name]
    category = ((status.get("statusCategory") or {}).get("key") or "").strip().lower()
    return _CATEGORY_TO_STATE.get(category, "new")


def map_priority(priority: Optional[dict]) -> Optional[str]:
    if not priority:
        return None
    name = (priority.get("name") or "").strip().lower()
    return _PRIORITY_MAP.get(name)


def _person(value) -> Optional[str]:
    """A Jira user object down to something displayable. Deliberately the
    display name rather than an account id: these become ticket text, and a
    directory-backed assignee is a separate concern (the `user` attribute
    type) rather than something to guess at here."""
    if not value:
        return None
    return _author_display_name(value)


# Jira Server is commonly published under a context path rather than at the
# host root — INFN's is at https://issues.infn.it/jira — and the site root
# still serves a normal web page, so the mistake looks like a working URL
# right up until the API returns 404 for a reason it doesn't explain.
_CONTEXT_PATH_CANDIDATES = ("", "/jira")


def resolve_api_base(jira, base_url: str) -> str:
    """The base URL whose REST API actually answers.

    serverInfo needs no authentication, so this also distinguishes "wrong
    URL" from "wrong token" before the first real request: a 404 here is the
    address, a 401 later is the credential.
    """
    tried = []
    for suffix in _CONTEXT_PATH_CANDIDATES:
        candidate = f"{base_url}{suffix}"
        url = f"{candidate}/rest/api/2/serverInfo"
        tried.append(url)
        try:
            resp = jira.get(url)
        except Exception:
            continue
        if resp.status_code == 404:
            continue
        # Anything else means something is listening on the API: 200, or a
        # 401 from an instance that doesn't expose serverInfo anonymously.
        if resp.status_code < 500:
            return candidate
    raise RuntimeError(
        "No Jira REST API found. Tried: " + ", ".join(tried) +
        ". Check the server URL — Jira is often published under a context "
        "path such as https://issues.infn.it/jira rather than the site root."
    )


def _search_issues(jira, base_url: str, jql: str, start_at: int) -> dict:
    resp = jira.get(
        f"{base_url}/rest/api/2/search",
        params={
            "jql": jql,
            "startAt": start_at,
            "maxResults": PAGE_SIZE,
            # Naming the fields keeps the payload to what is actually mapped;
            # a Jira issue with every field expanded is enormous.
            "fields": ",".join([
                "summary", "description", "status", "priority", "assignee",
                "reporter", "labels", "duedate", "resolutiondate", "created",
                "updated", "issuetype", "project", "components",
            ]),
        },
    )
    resp.raise_for_status()
    return resp.json()


def _import_comments(jira, base_url: str, issue: Issue, jira_key: str, db: Session,
                     job: ImportJob, seen: set) -> int:
    try:
        resp = jira.get(f"{base_url}/rest/api/2/issue/{jira_key}/comment")
        resp.raise_for_status()
        comments = resp.json().get("comments") or []
    except Exception as e:
        _record_diagnostic(job, seen, "comments", _describe_error(e, None))
        return 0

    existing = {
        c.uid for c in db.scalars(select(IssueComment).where(IssueComment.issue_uid == issue.uid))
    }
    added = 0
    for c in comments:
        uid = f"{issue.uid}-c{c.get('id')}"
        if uid in existing:
            continue
        db.add(IssueComment(
            uid=uid,
            issue_uid=issue.uid,
            author=_person(c.get("author")) or "unknown",
            body=c.get("body") or "",
        ))
        added += 1
    return added


# An Insight/Jira object key: letters and digits, a hyphen, then digits —
# "LNFT2-145356". Matched as whole words so a longer identifier that merely
# contains one isn't mistaken for it.
_KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")


def _link_mentioned_assets(
    db: Session, issue: Issue, text: str, key_to_asset: dict[str, str]
) -> int:
    """A ticket that names an asset key gets linked to that object.

    Jira's own Insight link fields are a paid add-on and not on every
    project, but the key ("LNFT2-145356") is routinely written into the
    summary or description — enough to connect work to equipment, which is
    the point of having both in one place.

    Candidate keys are pulled out of the text and looked up, rather than
    testing every asset against every ticket: with 3561 assets that second
    shape is millions of comparisons per import.
    """
    if not text:
        return 0
    jira_key = (issue.attributes or {}).get("jiraKey") or issue.uid
    linked = 0
    for candidate in set(_KEY_PATTERN.findall(text)):
        asset_uid = key_to_asset.get(candidate)
        if asset_uid is None:
            continue
        exists = db.scalar(
            select(AssetTicket).where(
                AssetTicket.asset_uid == asset_uid,
                AssetTicket.ticket_key == jira_key,
            )
        )
        if exists is None:
            now = datetime.now(timezone.utc)
            db.add(AssetTicket(
                uid=str(uuid.uuid4()),
                asset_uid=asset_uid,
                ticket_key=jira_key,
                summary=issue.title,
                type=(issue.attributes or {}).get("jiraIssueType") or "Task",
                status=issue.state,
                created=now,
                updated=now,
                backend_url=(issue.attributes or {}).get("jiraUrl"),
            ))
            linked += 1
        # The ticket's own asset_uid points at the first object named; the
        # rest are recorded as links, since a ticket has one subject but may
        # mention several.
        if issue.asset_uid is None:
            issue.asset_uid = asset_uid
    return linked


def run_jira_issue_import(
    job_uid: str,
    workspace_id: str,
    base_url: str,
    pat: str,
    jql: str,
    merge_strategy: str = "override",
    schema_uid: Optional[str] = None,
    link_assets: bool = True,
) -> None:
    db = SessionLocal()
    job = db.get(ImportJob, job_uid)
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    seen_diagnostics: set = set()
    base_url = base_url.rstrip("/")

    try:
        jira = _TimeoutSession()
        jira.headers.update({"Authorization": f"Bearer {pat}", "Accept": "application/json"})

        resolved_base = resolve_api_base(jira, base_url)
        if resolved_base != base_url:
            _set_progress(db, job, f"Jira API found at {resolved_base}")
        base_url = resolved_base

        if merge_strategy == "remove_all_before":
            removed = 0
            for issue in db.scalars(
                select(Issue).where(Issue.workspace_id == workspace_id)
            ):
                db.delete(issue)
                removed += 1
            db.commit()
            _set_progress(db, job, f"Removed {removed} existing ticket(s)")

        # Built once: the importer resolves asset keys mentioned in ticket
        # text, and rebuilding this per issue would dominate the run.
        key_to_asset = dict(
            db.execute(
                select(Asset.key, Asset.uid).where(Asset.workspace_id == workspace_id)
            ).all()
        ) if link_assets else {}

        _set_progress(db, job, "Searching Jira")
        start_at = 0
        total = None
        imported = comments_imported = links = 0

        while True:
            try:
                page = _search_issues(jira, base_url, jql, start_at)
            except Exception as e:
                raise RuntimeError(f"Jira search failed: {_describe_error(e, None)}") from e

            if total is None:
                total = page.get("total", 0)
                _set_progress(db, job, f"{total} issue(s) match")

            issues = page.get("issues") or []
            if not issues:
                break

            for jira_issue in issues:
                jira_key = jira_issue.get("key")
                if not jira_key:
                    continue
                fields = jira_issue.get("fields") or {}

                uid = f"{workspace_id}:{jira_key}"
                issue = db.get(Issue, uid)
                is_new = issue is None
                if is_new:
                    issue = Issue(uid=uid, workspace_id=workspace_id)

                if not should_write(
                    merge_strategy, is_new,
                    None if is_new else issue.updated_at,
                    _parse_jira_dt(fields.get("updated")),
                ):
                    continue

                issue.title = fields.get("summary") or jira_key
                issue.description = fields.get("description")
                issue.state = map_state(fields.get("status") or {})
                issue.priority = map_priority(fields.get("priority"))
                issue.assignee = _person(fields.get("assignee"))
                issue.created_by = _person(fields.get("reporter"))
                issue.labels = list(fields.get("labels") or [])
                issue.due_date = _parse_jira_dt(fields.get("duedate"))
                issue.closed_at = _parse_jira_dt(fields.get("resolutiondate"))
                if schema_uid:
                    issue.schema_uid = schema_uid

                # What Jira knows that our columns don't, kept rather than
                # discarded: the key is what a person searches for, and the
                # rest explains where the ticket came from.
                attributes = dict(issue.attributes or {})
                attributes.update({
                    "jiraKey": jira_key,
                    "jiraUrl": f"{base_url}/browse/{jira_key}",
                    "jiraIssueType": ((fields.get("issuetype") or {}).get("name")),
                    "jiraProject": ((fields.get("project") or {}).get("key")),
                    "jiraStatus": ((fields.get("status") or {}).get("name")),
                    "jiraComponents": [
                        c.get("name") for c in (fields.get("components") or []) if c.get("name")
                    ],
                })
                issue.attributes = attributes

                # One savepoint per issue: a bad row is skipped without
                # discarding the rest of the page, which a bare rollback here
                # would do — the page's earlier issues are uncommitted too.
                try:
                    with db.begin_nested():
                        db.add(issue)
                        db.flush()
                        comments = _import_comments(
                            jira, base_url, issue, jira_key, db, job, seen_diagnostics
                        )
                        asset_links = 0
                        if link_assets:
                            asset_links = _link_mentioned_assets(
                                db, issue, f"{issue.title}\n{issue.description or ''}",
                                key_to_asset,
                            )
                        db.flush()
                except Exception as e:
                    _set_progress(
                        db, job, f"Skipped {jira_key}: {_describe_error(e, None)}", errors=1
                    )
                    continue

                imported += 1
                comments_imported += comments
                links += asset_links

                if imported % 25 == 0:
                    db.commit()
                    _set_progress(db, job, f"{imported} of {total} issue(s)")

            db.commit()
            start_at += len(issues)
            if start_at >= (total or 0):
                break

        _set_progress(
            db, job, f"Imported {imported} ticket(s)",
            tickets=imported, comments=comments_imported, asset_links=links,
        )

        job.status = "succeeded"
        job.progress = "Import complete"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        db.rollback()
        job = db.get(ImportJob, job_uid)
        job.status = "failed"
        job.error = str(e)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()
