"""Import Confluence pages as documents.

Confluence is a source, like Jira: a page maps onto a Document with a
Revision holding its body, and what Confluence called things is kept as
provenance.

Two details shape the whole importer. Confluence stores pages as its own
XHTML-ish "storage format", not Markdown, so the body has to be converted
or it arrives as a wall of tags nobody can read or retrieve against. And
a page's *version* is the thing that changes: re-importing a page whose
version hasn't moved must not manufacture a new revision, or a document's
history fills with identical entries.
"""
import re
import uuid
from datetime import datetime, timezone
from html import unescape
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.document import Document, DocumentRelation, DocumentRevision
from app.models.import_job import ImportJob
from app.services.document_types import ensure_document_types, type_uid
from app.services.jira_import import (
    _TimeoutSession,
    _describe_error,
    _parse_jira_dt,
    _record_diagnostic,
    _set_progress,
)

PAGE_SIZE = 50

# A Confluence label, or a page title prefix, mapped onto one of our
# document types. Checked against labels first, then the title, and
# anything unrecognised becomes a Note rather than being forced into a
# category it doesn't belong to.
LABEL_TO_TYPE = {
    "procedure": "Procedure", "procedura": "Procedure", "sop": "Procedure",
    "work-instruction": "Work Instruction", "istruzione": "Work Instruction",
    "safety": "Safety Document", "sicurezza": "Safety Document",
    "radiation": "Safety Document", "interlock": "Safety Document",
    "specification": "Specification", "specifica": "Specification",
    "requirements": "Specification",
    "design": "Design Report", "design-report": "Design Report",
    "drawing": "Drawing", "disegno": "Drawing",
    "manual": "Manual", "manuale": "Manual",
    "commissioning": "Commissioning Record",
    "test-report": "Test Report", "test": "Test Report", "collaudo": "Test Report",
    "maintenance": "Maintenance Report", "manutenzione": "Maintenance Report",
    "logbook": "Logbook Entry", "elog": "Logbook Entry", "shift": "Logbook Entry",
    "runbook": "Runbook", "troubleshooting": "Runbook",
    "minutes": "Meeting Minutes", "verbale": "Meeting Minutes", "meeting": "Meeting Minutes",
}

TITLE_PREFIX_TO_TYPE = {
    "procedure": "Procedure", "procedura": "Procedure",
    "runbook": "Runbook",
    "minutes": "Meeting Minutes", "verbale": "Meeting Minutes",
    "test report": "Test Report",
    "manual": "Manual", "manuale": "Manual",
}

DEFAULT_TYPE = "Note"

# Confluence stores pages in its own XHTML dialect with <ac:…> and <ri:…>
# macro elements. Those carry the parts a person most needs — code blocks,
# warning panels, links to other pages and to attachments — and an HTML
# converter alone either drops them or renders their raw markup. So the
# macros are turned into ordinary HTML first, and markdownify does the rest
# properly: tables, nested lists and inline formatting are its job, not
# something to re-implement with regexes.

_PANEL_MACROS = {"info": "ℹ️", "note": "📝", "warning": "⚠️", "tip": "💡", "caution": "⚠️"}


def _macro_param(block: str, name: str) -> Optional[str]:
    match = re.search(
        rf'<ac:parameter[^>]*ac:name="{name}"[^>]*>(.*?)</ac:parameter>', block, re.S
    )
    return match.group(1).strip() if match else None


def _macro_body(block: str) -> str:
    match = re.search(
        r"<ac:(?:plain-text-body|rich-text-body)[^>]*>(.*?)</ac:(?:plain-text-body|rich-text-body)>",
        block, re.S,
    )
    if not match:
        return ""
    body = match.group(1)
    return re.sub(r"^<!\[CDATA\[|\]\]>$", "", body.strip())


def _convert_macro(match: re.Match) -> str:
    block = match.group(0)
    name = (match.group(1) or "").lower()
    body = _macro_body(block)

    if name in ("code", "noformat"):
        language = _macro_param(block, "language") or ""
        css = f' class="language-{language}"' if language else ""
        return f"<pre><code{css}>{body}</code></pre>"
    if name in _PANEL_MACROS:
        return f"<blockquote><p>{_PANEL_MACROS[name]} <strong>{name.title()}</strong></p>{body}</blockquote>"
    if name in ("toc", "children", "pagetree", "excerpt-include"):
        # Navigation furniture that means nothing outside Confluence.
        return ""
    if body:
        return body
    # A macro whose content lives only in Confluence — say so rather than
    # leaving a silent hole in the document.
    return f"<p><em>[{name} — see the original page]</em></p>"


def _confluence_macros_to_html(storage: str) -> str:
    html = re.sub(
        r'<ac:structured-macro[^>]*ac:name="([^"]+)".*?</ac:structured-macro>',
        _convert_macro, storage, flags=re.S,
    )
    html = re.sub(
        r'<ac:structured-macro[^>]*ac:name="([^"]+)"[^>]*/>',
        lambda m: "", html,
    )

    # A link to another page keeps its title; the URL is resolved by
    # whoever reads it, since page ids aren't portable.
    html = re.sub(
        r'<ac:link[^>]*>.*?<ri:page[^>]*ri:content-title="([^"]+)"[^>]*/>.*?</ac:link>',
        r"<a>\1</a>", html, flags=re.S,
    )
    html = re.sub(
        r'<ac:link[^>]*>.*?<ri:attachment[^>]*ri:filename="([^"]+)"[^>]*/>.*?</ac:link>',
        r"<em>attachment: \1</em>", html, flags=re.S,
    )
    html = re.sub(
        r'<ac:image[^>]*>.*?<ri:attachment[^>]*ri:filename="([^"]+)"[^>]*/>.*?</ac:image>',
        r"<p><em>image: \1</em></p>", html, flags=re.S,
    )
    html = re.sub(r"<ac:image[^>]*>.*?</ac:image>", "<p><em>image</em></p>", html, flags=re.S)
    # Whatever ac:/ri: markup is left would otherwise reach the reader raw.
    html = re.sub(r"</?(?:ac|ri):[^>]*>", "", html)
    return html


def _code_language(pre_element) -> str:
    code = pre_element.find("code") if hasattr(pre_element, "find") else None
    classes = (code.get("class") if code is not None else None) or []
    for name in classes:
        if name.startswith("language-"):
            return name.replace("language-", "")
    return ""


def storage_to_markdown(storage: str) -> str:
    """A Confluence page as Markdown.

    Macros become ordinary HTML first (above), then markdownify does the
    conversion — tables, nested lists and inline formatting are exactly the
    parts that are tedious and easy to get subtly wrong by hand.
    """
    if not storage:
        return ""
    from markdownify import markdownify

    html = _confluence_macros_to_html(storage)
    text = markdownify(
        html,
        heading_style="ATX",       # "## Heading", matching everything else here
        bullets="-",
        # markdownify hands this the <pre>; the language is on the <code>
        # inside it, which is where the macro conversion put it.
        code_language_callback=_code_language,
        # Equipment names are full of * and _; escaping them makes the text
        # harder to read without making it any safer.
        escape_asterisks=False,
        escape_underscores=False,
    )
    text = unescape(text)
    # markdownify is generous with blank lines around block elements.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def choose_document_type(labels: list[str], title: str) -> str:
    for label in labels:
        mapped = LABEL_TO_TYPE.get(label.strip().lower())
        if mapped:
            return mapped
    lowered = (title or "").strip().lower()
    for prefix, mapped in TITLE_PREFIX_TO_TYPE.items():
        if lowered.startswith(prefix):
            return mapped
    return DEFAULT_TYPE


def _person(value) -> Optional[str]:
    if not isinstance(value, dict):
        return None
    return value.get("displayName") or value.get("publicName") or value.get("username")


def _fetch_pages(session, base_url: str, space_key: Optional[str], cql: Optional[str],
                 start: int) -> dict:
    params = {
        "limit": PAGE_SIZE,
        "start": start,
        # body.storage is the page itself; the rest is what makes it
        # placeable and attributable.
        "expand": "body.storage,version,space,metadata.labels,history,ancestors",
    }
    if cql:
        params["cql"] = cql
        url = f"{base_url}/rest/api/content/search"
    else:
        params["type"] = "page"
        if space_key:
            params["spaceKey"] = space_key
        url = f"{base_url}/rest/api/content"
    resp = session.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


def resolve_api_base(session, base_url: str) -> str:
    """Confluence Server is often published under /confluence or /wiki, and
    the site root answers with a normal page either way — so a wrong base
    shows up as a 404 from the API and nothing more helpful."""
    tried = []
    for suffix in ("", "/confluence", "/wiki"):
        candidate = f"{base_url}{suffix}"
        url = f"{candidate}/rest/api/space"
        tried.append(url)
        try:
            resp = session.get(url, params={"limit": 1})
        except Exception:
            continue
        if resp.status_code == 404:
            continue
        if resp.status_code < 500:
            return candidate
    raise RuntimeError(
        "No Confluence REST API found. Tried: " + ", ".join(tried) +
        ". Check the server URL — Confluence is often published under a "
        "context path such as /confluence or /wiki rather than the site root."
    )


def _find_or_create_document(db: Session, workspace_id: str, space: Optional[str],
                            page_id: str, title: str) -> tuple[Document, str]:
    """The document this page maps to, creating it if new.

    Document codes are unique across the whole installation, not per
    workspace, so the readable "CONF-LNF-101" can only belong to one
    workspace. Two workspaces importing the same space is a legitimate
    thing to do — the second gets a qualified code rather than silently
    skipping the page, which is what happened before.
    """
    preferred = f"CONF-{space or 'X'}-{page_id}"
    existing = db.scalar(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.code.in_([preferred, f"{preferred}-{workspace_id}"]),
        )
    )
    if existing is not None:
        return existing, existing.code

    taken = db.scalar(select(Document).where(Document.code == preferred))
    code = preferred if taken is None else f"{preferred}-{workspace_id}"

    document = Document(
        uid=str(uuid.uuid4()),
        workspace_id=workspace_id,
        code=code,
        title=title,
        source="confluence",
    )
    db.add(document)
    db.flush()
    return document, code


def run_confluence_import(
    job_uid: str,
    workspace_id: str,
    base_url: str,
    pat: str,
    space_key: Optional[str] = None,
    cql: Optional[str] = None,
    merge_strategy: str = "override",
    link_assets: bool = True,
) -> None:
    db = SessionLocal()
    job = db.get(ImportJob, job_uid)
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()

    seen: set = set()
    base_url = base_url.rstrip("/")

    try:
        session = _TimeoutSession()
        session.headers.update({"Authorization": f"Bearer {pat}", "Accept": "application/json"})

        resolved = resolve_api_base(session, base_url)
        if resolved != base_url:
            _set_progress(db, job, f"Confluence API found at {resolved}")
        base_url = resolved

        type_uids = ensure_document_types(db, workspace_id)
        db.commit()

        # Asset keys mentioned in a page body become links, the same way
        # they do for tickets — a procedure that names a magnet should be
        # findable from that magnet.
        from app.models.asset import Asset

        key_to_asset = dict(
            db.execute(
                select(Asset.key, Asset.uid).where(Asset.workspace_id == workspace_id)
            ).all()
        ) if link_assets else {}
        key_pattern = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")

        if merge_strategy == "remove_all_before":
            removed = 0
            for document in db.scalars(
                select(Document).where(
                    Document.workspace_id == workspace_id, Document.source == "confluence"
                )
            ):
                db.delete(document)
                removed += 1
            db.commit()
            _set_progress(db, job, f"Removed {removed} previously imported document(s)")

        start = 0
        total = None
        imported = updated = skipped = links = 0

        while True:
            try:
                payload = _fetch_pages(session, base_url, space_key, cql, start)
            except Exception as e:
                raise RuntimeError(f"Confluence search failed: {_describe_error(e, None)}") from e

            results = payload.get("results") or []
            if total is None:
                total = payload.get("totalSize", payload.get("size", len(results)))
                _set_progress(db, job, f"{total} page(s) to import")
            if not results:
                break

            for page in results:
                page_id = str(page.get("id") or "")
                title = page.get("title") or f"Untitled {page_id}"
                if not page_id:
                    continue

                version = ((page.get("version") or {}).get("number")) or 1
                labels = [
                    label.get("name")
                    for label in (((page.get("metadata") or {}).get("labels") or {}).get("results") or [])
                    if label.get("name")
                ]
                space = ((page.get("space") or {}).get("key"))
                body = ((page.get("body") or {}).get("storage") or {}).get("value") or ""
                markdown = storage_to_markdown(body)
                web_url = f"{base_url}/pages/viewpage.action?pageId={page_id}"

                document, code = _find_or_create_document(
                    db, workspace_id, space, page_id, title
                )
                is_new = document.current_revision_uid is None

                document.title = title
                kind = choose_document_type(labels, title)
                document.document_type_uid = type_uids.get(kind) or type_uid(workspace_id, kind)

                attributes = {
                    "argus_source": "confluence",
                    "argus_source_id": page_id,
                    "argus_source_url": web_url,
                    "argus_source_space": space,
                    "argus_source_version": version,
                    "argus_source_updated": ((page.get("version") or {}).get("when")),
                    "argus_source_author": _person((page.get("version") or {}).get("by")),
                    "argus_keywords": labels,
                }

                current = (
                    db.get(DocumentRevision, document.current_revision_uid)
                    if document.current_revision_uid else None
                )
                # The page's version is what says whether anything changed.
                # Without this check every re-import would add a revision
                # identical to the last one.
                if current is not None and (current.attributes or {}).get(
                    "argus_source_version"
                ) == version:
                    skipped += 1
                    continue

                revision = DocumentRevision(
                    uid=str(uuid.uuid4()),
                    document_uid=document.uid,
                    revision_number=(current.revision_number + 1) if current else 1,
                    # Imported pages arrive published: they are already in
                    # use at the source, and parking them in "draft" would
                    # hide the entire library behind a review that nobody
                    # asked for.
                    state="published",
                    body_markdown=markdown,
                    attributes=attributes,
                    published_at=_parse_jira_dt((page.get("version") or {}).get("when")),
                )
                db.add(revision)
                db.flush()
                if current is not None:
                    current.state = "superseded"
                    current.superseded_by_uid = revision.uid
                document.current_revision_uid = revision.uid

                if is_new:
                    imported += 1
                else:
                    updated += 1

                if link_assets and markdown:
                    for candidate in set(key_pattern.findall(f"{title}\n{markdown}")):
                        asset_uid = key_to_asset.get(candidate)
                        if not asset_uid:
                            continue
                        exists = db.scalar(
                            select(DocumentRelation).where(
                                DocumentRelation.from_document_uid == document.uid,
                                DocumentRelation.to_type == "asset",
                                DocumentRelation.to_uid == asset_uid,
                            )
                        )
                        if exists is None:
                            db.add(DocumentRelation(
                                workspace_id=workspace_id,
                                from_document_uid=document.uid,
                                to_type="asset",
                                to_uid=asset_uid,
                                relation_type="describes",
                            ))
                            links += 1

                if (imported + updated) % 25 == 0:
                    db.commit()
                    _set_progress(db, job, f"{imported + updated} of {total} page(s)")

            db.commit()
            start += len(results)
            if total is not None and start >= total:
                break
            if len(results) < PAGE_SIZE:
                break

        _set_progress(
            db, job,
            f"Imported {imported} new and updated {updated} document(s)",
            documents=imported, documents_updated=updated,
            documents_unchanged=skipped, asset_links=links,
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
