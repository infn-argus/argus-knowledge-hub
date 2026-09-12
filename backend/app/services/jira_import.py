"""Import schemas + assets from a Jira Insight/Assets object schema.

Consolidates the logic already built and verified live against
servicedesk.infn.it during interactive sessions (attribute/hierarchy
type-mapping, icon crawl, attribute-value backfill) into one reusable,
UI-triggered background job.
"""
import os
import uuid
from datetime import datetime, timezone

import requests
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from sqlalchemy import select

from app.db import SessionLocal
from app.models.asset import Asset, Relation
from app.models.asset_subresources import AssetComment, AssetHistory
from app.models.attachment import Attachment
from app.models.global_value import GlobalValue
from app.models.import_job import ImportJob
from app.models.schema import Schema
from app.services.attribute_validation import _descendant_schema_uids, check_attributes
from app.services.import_merge import should_write

ATTACHMENTS_DIR = os.environ.get("ATTACHMENTS_DIR", "/data/attachments")

DEFAULT_TYPE_MAP = {
    "text": "string",
    "textarea": "text",
    "integer": "integer",
    "float": "float",
    "double": "float",
    "boolean": "boolean",
    "date": "date",
    "datetime": "datetime",
    "url": "string",
    "email": "string",
    "ipaddress": "string",
    # Jira's native "User" attribute type — the value comes through as a
    # display name (see _pick_attribute_value's nested "user" fallback), not
    # one of our own User ids, so it'll surface as a missing reference until
    # a workspace "Relink" resolves it by matching name/email.
    "user": "user",
}


def _map_attribute(jira_attr: dict) -> dict:
    key = jira_attr["name"].lower().replace(" ", "_").replace("/", "_")
    out = {
        "id": str(jira_attr["id"]),
        "name": jira_attr["name"],
        "key": key,
        "required": (jira_attr.get("minimumCardinality") or 0) > 0,
        "multiValue": (jira_attr.get("maximumCardinality") or 1) != 1,
        "readOnly": not jira_attr.get("editable", True),
        "visible": not jira_attr.get("hidden", False),
    }
    if jira_attr.get("referenceObjectTypeId") is not None:
        out["type"] = "reference"
        ref = jira_attr.get("referenceType") or {}
        out["referenceType"] = ref.get("name") or str(jira_attr["referenceObjectTypeId"])
        # Resolved to our own Schema.uid in a later pass, once every type
        # from this run (and any earlier run) is available to look up —
        # see _resolve_reference_schema_uid.
        out["_jiraReferenceObjectTypeId"] = jira_attr["referenceObjectTypeId"]
        return out

    if jira_attr.get("type") == 7:  # Status: schema-scoped, shared options -> Global Value
        out["type"] = "enumeration"
        out["key"] = "status"
        out["global"] = True
        return out

    default_type_name = ((jira_attr.get("defaultType") or {}).get("name") or "").lower()
    out["type"] = DEFAULT_TYPE_MAP.get(default_type_name, "string")
    if jira_attr.get("options"):
        opts = [o.strip() for o in jira_attr["options"].split(",") if o.strip()]
        if opts:
            out["type"] = "enumeration"
            out["options"] = [{"id": o.lower().replace(" ", "_"), "value": o} for o in opts]
    return out


def _fetch_jira_objects(jira: requests.Session, base_url: str, jira_schema_id: str, object_type_id: int):
    all_objects = []
    page = 1
    while True:
        payload = {
            "objectTypeId": object_type_id,
            "objectSchemaId": jira_schema_id,
            "filters": [],
            "attributesToDisplay": {"attributesToDisplayIds": []},
            "page": page,
            "asc": 1,
            "resultsPerPage": 50,
            "includeAttributes": True,
        }
        resp = jira.post(f"{base_url}/rest/insight/1.0/object/navlist", json=payload)
        resp.raise_for_status()
        data = resp.json()
        entries = data.get("objectEntries") or []
        all_objects.extend(entries)
        page_size = data.get("pageSize", 1)
        if page >= page_size or not entries:
            break
        page += 1
    return all_objects


def _pick_attribute_value(v: dict):
    """A cell's value shape varies by Jira Insight attribute type: plain
    text/number attributes carry it directly under displayValue/value, but
    "User"/"Group"/reference-like attribute types nest it under an object
    (e.g. {"user": {"displayName": ...}}) — try the common direct keys first,
    then fall back to the known nested shapes so those values aren't
    silently dropped."""
    for key in ("displayValue", "value"):
        val = v.get(key)
        if val not in (None, ""):
            return val
    for nested_key in ("user", "group", "project", "version", "referencedObject"):
        nested = v.get(nested_key)
        if isinstance(nested, dict):
            for key in ("displayName", "name", "label", "value", "key"):
                val = nested.get(key)
                if val not in (None, ""):
                    return val
    return None


def _build_attribute_values(jira_object: dict, attr_map: dict) -> tuple[dict, list[tuple[str, str]]]:
    """Returns (attributes dict, [(relation_type, referenced_object_key), ...])."""
    out = {}
    relation_links: list[tuple[str, str]] = []
    for cell in jira_object.get("attributes") or []:
        attr_id = (cell.get("objectTypeAttribute") or {}).get("id") or cell.get(
            "objectTypeAttributeId"
        )
        if attr_id is None or attr_id not in attr_map:
            continue
        meta = attr_map[attr_id]
        values = cell.get("objectAttributeValues") or []
        picked = [p for p in (_pick_attribute_value(v) for v in values) if p is not None]
        if picked:
            out[meta["key"]] = picked if meta["multiValue"] else picked[0]

        if meta.get("is_reference"):
            for v in values:
                ref_key = (v.get("referencedObject") or {}).get("objectKey")
                if ref_key:
                    relation_links.append((meta["name"], ref_key))
    return out, relation_links


def _parse_jira_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _download_attachment(
    jira: requests.Session,
    workspace_id: str,
    url: str,
    filename: str,
    mime_type: str | None = None,
    author: str | None = None,
    backend_id: str | None = None,
    backend_url: str | None = None,
) -> Attachment:
    resp = jira.get(url)
    resp.raise_for_status()
    att_uid = str(uuid.uuid4())
    storage_path = os.path.join(ATTACHMENTS_DIR, att_uid)
    with open(storage_path, "wb") as f:
        f.write(resp.content)
    return Attachment(
        uid=att_uid,
        workspace_id=workspace_id,
        filename=filename,
        mime_type=mime_type or resp.headers.get("Content-Type"),
        file_size=len(resp.content),
        author=author,
        storage_path=storage_path,
        backend_id=backend_id,
        backend_url=backend_url,
    )


def _describe_error(exc: Exception, resp: "requests.Response | None") -> str:
    if resp is not None:
        snippet = (resp.text or "")[:200].replace("\n", " ")
        return f"HTTP {resp.status_code} at {resp.url} — {snippet}"
    return f"{type(exc).__name__}: {exc}"


def _get_json(jira: requests.Session, urls: list[str]):
    """Try each candidate URL in order (Insight's REST layout differs across
    deployments/versions) — returns (data, None) on the first success, or
    (None, description-of-last-failure) if every candidate failed, so a
    genuinely wrong/unavailable endpoint is diagnosable instead of silently
    producing nothing."""
    last_error = None
    for url in urls:
        try:
            resp = jira.get(url)
            resp.raise_for_status()
            return resp.json(), None
        except requests.HTTPError as e:
            last_error = _describe_error(e, e.response)
        except Exception as e:
            last_error = _describe_error(e, None)
    return None, last_error


def _author_display_name(value) -> "str | None":
    """The author/actor field on attachments/comments/history varies by
    Jira version: sometimes a {"displayName": ...} object, sometimes a
    plain username string. Handle both rather than assuming the shape and
    crashing the whole enrichment step for that object."""
    if isinstance(value, dict):
        return value.get("displayName") or value.get("name") or value.get("key")
    if isinstance(value, str) and value:
        return value
    return None


def _resolve_reference_schema_uid(db: Session, jira_object_type_id, jira_id_to_uid: dict):
    """A reference attribute's target type may have been imported in this
    same run, or — for shared infrastructure imported once into its own
    (often global) workspace and referenced from several others — in an
    earlier, separate import. Check the in-memory map from this run first,
    then fall back to any previously-imported schema tagged with this Jira
    object type id, in any workspace."""
    if jira_object_type_id in jira_id_to_uid:
        return jira_id_to_uid[jira_object_type_id]
    match = (
        db.query(Schema)
        .filter(Schema.metadata_json["jiraObjectTypeId"].as_integer() == jira_object_type_id)
        .first()
    )
    return match.uid if match else None


def resolve_reference_attributes(db: Session, jira_id_to_uid: dict) -> None:
    """Reference attributes only carry the *Jira* target type id until now —
    resolve each to our own Schema.uid once every type from this run (and
    any earlier run) can be looked up. Does not commit; the caller decides
    when."""
    for schema_uid in jira_id_to_uid.values():
        schema = db.get(Schema, schema_uid)
        changed = False
        for attr in schema.attributes or []:
            if attr.get("type") != "reference" or attr.get("referenceSchemaUid"):
                continue
            raw_ref_id = attr.get("_jiraReferenceObjectTypeId")
            if raw_ref_id is None:
                continue
            resolved = _resolve_reference_schema_uid(db, raw_ref_id, jira_id_to_uid)
            if resolved:
                attr["referenceSchemaUid"] = resolved
                # Jira Insight commonly uses a shallow category/leaf
                # hierarchy (e.g. "HW Model" with 19 concrete subtypes and
                # no instances of its own) — a reference to the category
                # only ever resolves if it can also match the category's
                # descendants, exactly like our own reference-picker does.
                if _descendant_schema_uids(db, resolved):
                    attr["includeChildren"] = True
                changed = True
        if changed:
            # In-place dict mutation above means old/new compare equal by
            # value (same dict objects either side) — SQLAlchemy won't
            # detect the JSONB column as dirty without this.
            flag_modified(schema, "attributes")


def _record_diagnostic(job: ImportJob, seen: set, category: str, detail: str) -> None:
    """Records at most one warning per failure category per run — otherwise
    a systemically-wrong endpoint would add one warning per asset."""
    if category in seen:
        return
    seen.add(category)
    job.warnings = [*(job.warnings or []), f"{category}: {detail}"]


def _import_object_avatar(
    jira: requests.Session,
    base_url: str,
    workspace_id: str,
    asset: Asset,
    jo: dict,
    obj_id,
    schema_icon_url: str | None,
    db: Session,
    job: ImportJob,
    seen: set,
) -> None:
    avatar = jo.get("avatar")
    if avatar is None:
        data, error = _get_json(jira, [f"{base_url}/rest/insight/1.0/object/{obj_id}"])
        if error:
            _record_diagnostic(job, seen, "avatar", error)
            return
        avatar = (data or {}).get("avatar")
    if not avatar:
        return
    avatar_url = avatar.get("url48") or avatar.get("url72") or avatar.get("url16")
    if not avatar_url or avatar_url == schema_icon_url:
        return
    backend_id = f"avatar:{obj_id}"
    existing = (
        db.query(Attachment)
        .filter(Attachment.asset_uid == asset.uid, Attachment.backend_id == backend_id)
        .first()
    )
    if existing:
        asset.avatar_icon_uid = existing.uid
        return
    att = _download_attachment(
        jira, workspace_id, avatar_url, filename=f"{asset.key}-avatar.png",
        mime_type="image/png", backend_id=backend_id,
    )
    att.asset_uid = asset.uid
    db.add(att)
    db.flush()
    asset.avatar_icon_uid = att.uid


def _import_object_attachments(
    jira: requests.Session, base_url: str, workspace_id: str, asset: Asset, obj_id, db: Session,
    job: ImportJob, seen: set,
) -> int:
    remote_attachments, error = _get_json(jira, [
        f"{base_url}/rest/insight/1.0/attachments/object/{obj_id}",
        f"{base_url}/rest/insight/1.0/object/{obj_id}/attachments",
    ])
    if error:
        _record_diagnostic(job, seen, "attachments", error)
        return 0
    imported = 0
    for a in remote_attachments or []:
        backend_id = str(a.get("id"))
        existing = (
            db.query(Attachment)
            .filter(Attachment.asset_uid == asset.uid, Attachment.backend_id == backend_id)
            .first()
        )
        if existing:
            continue
        try:
            att = _download_attachment(
                jira, workspace_id, f"{base_url}/rest/insight/1.0/attachments/{a['id']}",
                filename=a.get("filename") or backend_id,
                mime_type=a.get("mimeType"),
                author=_author_display_name(a.get("author")),
                backend_id=backend_id,
            )
        except Exception as e:
            _record_diagnostic(job, seen, "attachment_download", _describe_error(e, getattr(e, "response", None)))
            continue
        att.asset_uid = asset.uid
        db.add(att)
        imported += 1
    return imported


def _import_object_history(
    jira: requests.Session, base_url: str, workspace_id: str, asset: Asset, obj_id, db: Session,
    job: ImportJob, seen: set,
) -> int:
    remote_history, error = _get_json(jira, [
        f"{base_url}/rest/insight/1.0/object/{obj_id}/history",
        f"{base_url}/rest/insight/1.0/history/object/{obj_id}",
    ])
    if error:
        _record_diagnostic(job, seen, "history", error)
        return 0
    imported = 0
    for h in remote_history or []:
        backend_id = str(h.get("id") or h.get("historyId") or "")
        if not backend_id:
            continue
        existing = (
            db.query(AssetHistory)
            .filter(AssetHistory.asset_uid == asset.uid, AssetHistory.backend_id == backend_id)
            .first()
        )
        if existing:
            continue
        actor = h.get("actor") or h.get("author") or h.get("updatedBy")
        timestamp = (
            _parse_jira_dt(h.get("created") or h.get("updated") or h.get("timestamp"))
            or datetime.now(timezone.utc)
        )
        details = h.get("description") or h.get("message") or h.get("affectedAttribute") or str(h)
        db.add(AssetHistory(
            uid=str(uuid.uuid4()),
            asset_uid=asset.uid,
            type=h.get("type") or h.get("action") or "update",
            author=_author_display_name(actor) or "Jira",
            details=str(details),
            timestamp=timestamp,
            backend_id=backend_id,
        ))
        imported += 1
    return imported


def _import_object_comments(
    jira: requests.Session, base_url: str, workspace_id: str, asset: Asset, obj_id, db: Session,
    job: ImportJob, seen: set,
) -> int:
    remote_comments, error = _get_json(jira, [
        f"{base_url}/rest/insight/1.0/comment/object/{obj_id}",
        f"{base_url}/rest/insight/1.0/object/{obj_id}/comment",
        f"{base_url}/rest/insight/1.0/object/{obj_id}/comments",
    ])
    if error:
        _record_diagnostic(job, seen, "comments", error)
        return 0
    imported = 0
    for c in remote_comments or []:
        backend_id = str(c.get("id"))
        existing = (
            db.query(AssetComment)
            .filter(AssetComment.asset_uid == asset.uid, AssetComment.backend_id == backend_id)
            .first()
        )
        if existing:
            continue
        created = _parse_jira_dt(c.get("created")) or _parse_jira_dt(c.get("updated")) or datetime.now(timezone.utc)
        updated = _parse_jira_dt(c.get("updated")) or created
        db.add(AssetComment(
            uid=str(uuid.uuid4()),
            asset_uid=asset.uid,
            author=_author_display_name(c.get("author")) or "Jira",
            text=c.get("comment") or "",
            created=created,
            updated=updated,
            backend_id=backend_id,
        ))
        imported += 1
    return imported


def _set_progress(db: Session, job: ImportJob, message: str, **count_updates):
    job.progress = message
    if count_updates:
        counts = dict(job.counts or {})
        for k, v in count_updates.items():
            counts[k] = counts.get(k, 0) + v
        job.counts = counts
    db.commit()


def _add_warnings(db: Session, job: ImportJob, key: str, violations: list[str]) -> None:
    if not violations:
        return
    job.warnings = [*(job.warnings or []), f"{key}: {'; '.join(violations)}"]
    counts = dict(job.counts or {})
    counts["constraint_warnings"] = counts.get("constraint_warnings", 0) + 1
    job.counts = counts


def run_jira_import(
    job_uid: str,
    workspace_id: str,
    base_url: str,
    pat: str,
    jira_schema_id: str,
    merge_strategy: str = "override",
):
    db = SessionLocal()
    job = db.get(ImportJob, job_uid)
    seen_diagnostics: set = set()
    try:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        if merge_strategy == "remove_all_before":
            wiped = (
                db.query(Schema)
                .filter(
                    Schema.workspace_id == workspace_id,
                    Schema.metadata_json["source"].astext == "jira",
                )
                .delete(synchronize_session=False)
            )
            db.commit()
            _set_progress(db, job, f"Removed {wiped} previously-imported type(s) before reimporting")

        jira = requests.Session()
        jira.headers.update({"Authorization": f"Bearer {pat}"})

        types_resp = jira.get(
            f"{base_url}/rest/insight/1.0/objectschema/{jira_schema_id}/objecttypes/flat"
        )
        types_resp.raise_for_status()
        object_types = types_resp.json()
        _set_progress(db, job, f"Found {len(object_types)} object types")

        status_resp = jira.get(
            f"{base_url}/rest/insight/1.0/config/statustype",
            params={"objectSchemaId": jira_schema_id},
        )
        status_resp.raise_for_status()
        status_types = status_resp.json()
        if status_types:
            global_status = (
                db.query(GlobalValue)
                .filter(GlobalValue.workspace_id == workspace_id, GlobalValue.key == "status")
                .first()
            ) or GlobalValue(uid=str(uuid.uuid4()), workspace_id=workspace_id, key="status")
            global_status.name = "Status"
            global_status.type = "enumeration"
            global_status.options = [
                {"id": s["name"].lower().replace(" ", "_"), "value": s["name"]}
                for s in status_types
            ]
            db.add(global_status)
            db.commit()

        jira_id_to_uid: dict = {}
        schema_attr_maps: dict = {}
        schema_icon_urls: dict = {}

        os.makedirs(ATTACHMENTS_DIR, exist_ok=True)

        for t in object_types:
            jid = t["id"]
            existing = (
                db.query(Schema)
                .filter(
                    Schema.workspace_id == workspace_id,
                    Schema.metadata_json["jiraObjectTypeId"].as_integer() == jid,
                )
                .first()
            )
            schema = existing or Schema(uid=str(uuid.uuid4()), workspace_id=workspace_id)
            schema.name = t["name"]
            schema.is_concrete = True
            schema.metadata_json = {"source": "jira", "jiraObjectTypeId": jid}

            attrs_resp = jira.get(f"{base_url}/rest/insight/1.0/objecttype/{jid}/attributes")
            attrs_resp.raise_for_status()
            jira_attrs = attrs_resp.json()
            mapped_attrs = [_map_attribute(a) for a in jira_attrs]
            schema.attributes = mapped_attrs
            schema_attr_maps[jid] = {
                int(a["id"]): {
                    "key": a["key"],
                    "name": a["name"],
                    "multiValue": bool(a.get("multiValue")),
                    "is_reference": a["type"] == "reference",
                }
                for a in mapped_attrs
            }

            try:
                icon_type_resp = jira.get(f"{base_url}/rest/insight/1.0/objecttype/{jid}")
                icon = icon_type_resp.json().get("icon") or {}
                icon_url = icon.get("url48") or icon.get("url16")
                schema_icon_urls[jid] = icon_url
                if icon_url and not schema.icon_attachment_uid:
                    att = _download_attachment(
                        jira, workspace_id, icon_url, filename=f"{jid}.png", mime_type="image/png",
                    )
                    db.add(att)
                    db.flush()
                    schema.icon_attachment_uid = att.uid
            except Exception:
                schema_icon_urls[jid] = None

            db.add(schema)
            db.flush()
            jira_id_to_uid[jid] = schema.uid
            _set_progress(db, job, f"Imported schema: {t['name']}", schemas=1)

        for t in object_types:
            jid = t["id"]
            parent_jid = t.get("parentObjectTypeId")
            if parent_jid is not None and parent_jid in jira_id_to_uid:
                schema = db.get(Schema, jira_id_to_uid[jid])
                schema.parent_schema_uid = jira_id_to_uid[parent_jid]
        db.commit()

        resolve_reference_attributes(db, jira_id_to_uid)
        db.commit()

        pending_relations: list[tuple[str, str, str]] = []  # (from_key, to_key, relation_type)

        for t in object_types:
            jid = t["id"]
            if t.get("abstractObjectType"):
                # Jira's navlist returns every descendant object when queried with an
                # abstract type's id, not just objects of that type — crawling it here
                # would stomp the correct type/schema already set by its concrete
                # descendants (and drop attributes not defined on the abstract parent).
                continue
            attr_map = schema_attr_maps[jid]
            try:
                jira_objects = _fetch_jira_objects(jira, base_url, jira_schema_id, jid)
            except Exception as e:
                _set_progress(db, job, f"Error listing objects for {t['name']}: {e}", errors=1)
                continue

            own_objects = 0
            attachments_imported = 0
            comments_imported = 0
            history_imported = 0
            for jo in jira_objects:
                key = jo.get("objectKey")
                if not key:
                    continue
                # Jira's navlist recurses into child types for any type that has
                # children (not just abstract ones) — e.g. querying "bpm" also
                # returns its "cpu" children. Only handle objects that actually
                # belong to the type being crawled; a descendant object is handled
                # correctly when its own type is iterated.
                if (jo.get("objectType") or {}).get("id") != jid:
                    continue
                own_objects += 1
                asset = db.query(Asset).filter(
                    Asset.workspace_id == workspace_id, Asset.key == key
                ).first()
                is_new = asset is None
                if is_new:
                    asset = Asset(
                        uid=str(uuid.uuid4()),
                        workspace_id=workspace_id,
                        key=key,
                    )

                write = should_write(
                    merge_strategy,
                    is_new,
                    None if is_new else asset.updated_at,
                    _parse_jira_dt(jo.get("updated")),
                )
                relation_links: list[tuple[str, str]] = []
                if write:
                    asset.schema_uid = jira_id_to_uid[jid]
                    asset.name = jo.get("label") or key
                    asset.type = t["name"]
                    attributes, relation_links = _build_attribute_values(jo, attr_map)
                    asset.attributes = attributes

                    # Non-fatal: Jira data doesn't always meet constraints
                    # configured after the fact (unique/cardinality/regex) —
                    # the import still proceeds, this is just surfaced for
                    # review. Reference-type checks are skipped: Jira reference
                    # values are display labels resolved via the separate
                    # Relation mechanism below, not asset uids.
                    schema_obj = db.get(Schema, jira_id_to_uid[jid])
                    violations = check_attributes(
                        db, schema_obj, attributes, workspace_id, Asset,
                        exclude_uid=asset.uid, skip_reference=True,
                    )
                    _add_warnings(db, job, key, violations)

                db.add(asset)
                try:
                    db.flush()
                except Exception:
                    db.rollback()
                    _set_progress(db, job, f"Skipped {key}: constraint violation", errors=1)
                    continue

                obj_id = jo.get("id") or jo.get("objectId")
                if obj_id is None:
                    _record_diagnostic(
                        job, seen_diagnostics, "object_id",
                        f"navlist entries have no 'id'/'objectId' field — got keys {sorted(jo.keys())}; "
                        "avatar/attachments/comments/history cannot be fetched per-object",
                    )
                else:
                    try:
                        with db.begin_nested():
                            _import_object_avatar(
                                jira, base_url, workspace_id, asset, jo, obj_id,
                                schema_icon_urls.get(jid), db, job, seen_diagnostics,
                            )
                            attachments_imported += _import_object_attachments(
                                jira, base_url, workspace_id, asset, obj_id, db, job, seen_diagnostics,
                            )
                            comments_imported += _import_object_comments(
                                jira, base_url, workspace_id, asset, obj_id, db, job, seen_diagnostics,
                            )
                            history_imported += _import_object_history(
                                jira, base_url, workspace_id, asset, obj_id, db, job, seen_diagnostics,
                            )
                    except Exception as e:
                        _record_diagnostic(job, seen_diagnostics, "enrichment", _describe_error(e, None))

                for relation_type, ref_key in relation_links:
                    pending_relations.append((key, ref_key, relation_type))

            db.commit()
            _set_progress(
                db, job, f"Imported {own_objects} objects for {t['name']}",
                assets=own_objects, attachments=attachments_imported, comments=comments_imported,
                history=history_imported,
            )

        # Reference attributes can point across object types processed in any
        # order, so relations are resolved only now that every asset in the
        # schema has been created and has a known key -> uid mapping.
        if pending_relations:
            key_to_uid = dict(
                db.execute(
                    select(Asset.key, Asset.uid).where(Asset.workspace_id == workspace_id)
                ).all()
            )
            existing_relations = {
                (r.from_asset_uid, r.to_asset_uid, r.relation_type)
                for r in db.scalars(
                    select(Relation).where(Relation.workspace_id == workspace_id)
                )
            }
            relations_created = 0
            for from_key, to_key, relation_type in pending_relations:
                from_uid = key_to_uid.get(from_key)
                to_uid = key_to_uid.get(to_key)
                if from_uid is None or to_uid is None:
                    continue
                dedup_key = (from_uid, to_uid, relation_type)
                if dedup_key in existing_relations:
                    continue
                existing_relations.add(dedup_key)
                db.add(Relation(
                    workspace_id=workspace_id,
                    from_asset_uid=from_uid,
                    to_asset_uid=to_uid,
                    relation_type=relation_type,
                ))
                relations_created += 1
            db.commit()
            _set_progress(db, job, f"Created {relations_created} relations", relations=relations_created)

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
