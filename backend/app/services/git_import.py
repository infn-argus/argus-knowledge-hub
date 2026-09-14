"""Import schemas + assets from a Git repository, using the same file layout
the Flutter app's git backend already writes: `schemas/{name}.yaml` and
`assets/{schema}/{uid}.json` (see lib/adapters/git/mappers/*.dart).
"""
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import quote, urlparse

import requests
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.asset import Asset, Relation
from app.models.import_job import ImportJob
from app.models.schema import Schema
from app.services.import_merge import should_write


def _parse_repo(repo_url: str) -> tuple[str, str]:
    """Returns (owner, repo) from a GitHub/GitLab URL."""
    path = urlparse(repo_url).path.strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    parts = path.split("/")
    return parts[0], "/".join(parts[1:])


def github_api(repo_url: str) -> str:
    """Where this repository's API lives.

    Self-hosted instances are the normal case here, not the exception:
    these repositories are on baltig.infn.it, and an API address fixed at
    github.com or gitlab.com can only ever read somebody else's.
    """
    host = (urlparse(repo_url).netloc or "github.com").lower()
    if host in ("github.com", "www.github.com", "api.github.com"):
        return "https://api.github.com"
    return f"https://{host}/api/v3"


def gitlab_api(repo_url: str) -> str:
    host = (urlparse(repo_url).netloc or "gitlab.com").lower()
    return f"https://{host}/api/v4"


def _checked(resp: requests.Response, what: str, authenticated: bool) -> requests.Response:
    """raise_for_status, with the sentence a person needs instead of a code.

    404 and 401 mean the same thing from the outside when no token was
    given — the repository is private, or it is not there — and "404 Client
    Error" sends somebody to check their spelling when the answer is that
    they need a token.
    """
    if resp.status_code in (401, 403, 404):
        if not authenticated:
            raise RuntimeError(
                f"{what} could not be read ({resp.status_code}). If this repository is "
                f"private, add a personal access token; public repositories need none."
            )
        raise RuntimeError(
            f"{what} could not be read ({resp.status_code}). Check the repository path, "
            f"the branch, and that the token has read access to it."
        )
    resp.raise_for_status()
    return resp


def _list_files_github(session: requests.Session, owner: str, repo: str, branch: str,
                       api: str = "https://api.github.com"):
    resp = _checked(session.get(
        f"{api}/repos/{owner}/{repo}/git/trees/{branch}",
        params={"recursive": "1"},
    ), f"{owner}/{repo}@{branch}", "Authorization" in session.headers)
    return [
        item["path"] for item in resp.json().get("tree", []) if item.get("type") == "blob"
    ]


def _get_file_github(session: requests.Session, owner: str, repo: str, path: str, branch: str,
                     api: str = "https://api.github.com") -> str:
    resp = _checked(session.get(
        f"{api}/repos/{owner}/{repo}/contents/{quote(path)}",
        params={"ref": branch},
        headers={"Accept": "application/vnd.github.v3.raw"},
    ), f"{path} in {owner}/{repo}@{branch}", "Authorization" in session.headers)
    return resp.text


def _list_files_gitlab(session: requests.Session, project_path: str, branch: str,
                       api: str = "https://gitlab.com/api/v4"):
    project_id = quote(project_path, safe="")
    files = []
    page = 1
    while True:
        resp = _checked(session.get(
            f"{api}/projects/{project_id}/repository/tree",
            params={"ref": branch, "recursive": "true", "per_page": 100, "page": page},
        ), f"{project_path}@{branch}", "PRIVATE-TOKEN" in session.headers)
        batch = resp.json()
        files.extend(item["path"] for item in batch if item.get("type") == "blob")
        if len(batch) < 100:
            break
        page += 1
    return files


def _get_file_gitlab(session: requests.Session, project_path: str, path: str, branch: str,
                     api: str = "https://gitlab.com/api/v4") -> str:
    project_id = quote(project_path, safe="")
    resp = _checked(session.get(
        f"{api}/projects/{project_id}/repository/files/{quote(path, safe='')}/raw",
        params={"ref": branch},
    ), f"{path} in {project_path}@{branch}", "PRIVATE-TOKEN" in session.headers)
    return resp.text


def _parse_content(path: str, text: str) -> dict:
    if path.endswith((".yaml", ".yml")):
        return yaml.safe_load(text)
    return __import__("json").loads(text)


def _parse_git_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def run_git_import(
    job_uid: str,
    workspace_id: str,
    provider: str,
    repo_url: str,
    pat: str,
    branch: str,
    merge_strategy: str = "override",
):
    db = SessionLocal()
    job = db.get(ImportJob, job_uid)
    try:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        if merge_strategy == "remove_all_before":
            wiped = (
                db.query(Schema)
                .filter(
                    Schema.workspace_id == workspace_id,
                    Schema.metadata_json["source"].astext == "git",
                )
                .delete(synchronize_session=False)
            )
            db.commit()
            job.progress = f"Removed {wiped} previously-imported type(s) before reimporting"
            db.commit()

        session = requests.Session()
        owner, repo = _parse_repo(repo_url)

        if provider == "github":
            api = github_api(repo_url)
            # No token at all rather than an empty one: GitHub rejects
            # "Bearer " outright, so sending it turns a readable public
            # repository into a 401.
            if pat:
                session.headers.update({"Authorization": f"Bearer {pat}"})
            list_files = lambda: _list_files_github(session, owner, repo, branch, api)
            get_file = lambda p: _get_file_github(session, owner, repo, p, branch, api)
        else:
            api = gitlab_api(repo_url)
            if pat:
                session.headers.update({"PRIVATE-TOKEN": pat})
            project_path = f"{owner}/{repo}"
            list_files = lambda: _list_files_gitlab(session, project_path, branch, api)
            get_file = lambda p: _get_file_gitlab(session, project_path, p, branch, api)

        all_paths = list_files()
        job.progress = f"Found {len(all_paths)} files in repo"
        db.commit()

        schema_paths = [p for p in all_paths if re.match(r"^schemas/[^/]+\.(ya?ml|json)$", p)]
        asset_paths = [p for p in all_paths if re.match(r"^assets/[^/]+/[^/]+\.json$", p)]

        git_uid_to_uid: dict = {}
        schemas_imported = 0
        for p in schema_paths:
            try:
                data = _parse_content(p, get_file(p))
            except Exception:
                continue
            if not data or not data.get("name"):
                continue

            git_uid = data.get("uid") or p
            existing = (
                db.query(Schema)
                .filter(
                    Schema.workspace_id == workspace_id,
                    Schema.metadata_json["gitUid"].astext == git_uid,
                )
                .first()
            )
            schema = existing or Schema(uid=str(uuid.uuid4()), workspace_id=workspace_id)
            schema.name = data["name"]
            schema.description = data.get("description")
            schema.is_concrete = data.get("isConcrete", True)
            schema.attributes = data.get("attributes") or []
            schema.metadata_json = {
                **(data.get("metadata") or {}),
                "source": "git",
                "gitUid": git_uid,
                "gitPath": p,
            }
            db.add(schema)
            db.flush()
            git_uid_to_uid[git_uid] = schema.uid
            schemas_imported += 1
            job.progress = f"Imported schema: {schema.name}"
            db.commit()

        # Second pass: resolve parentSchemaUid references now that all schemas exist.
        for p in schema_paths:
            try:
                data = _parse_content(p, get_file(p))
            except Exception:
                continue
            if not data:
                continue
            git_uid = data.get("uid") or p
            parent_git_uid = data.get("parentSchemaUid")
            if git_uid in git_uid_to_uid and parent_git_uid in git_uid_to_uid:
                schema = db.get(Schema, git_uid_to_uid[git_uid])
                schema.parent_schema_uid = git_uid_to_uid[parent_git_uid]
        db.commit()

        assets_imported = 0
        errors = 0
        asset_git_uid_to_uid: dict = {}
        pending_relations: list[tuple[str, str]] = []  # (from_git_uid, to_git_uid)
        for p in asset_paths:
            try:
                data = _parse_content(p, get_file(p))
            except Exception:
                errors += 1
                continue
            if not data or not data.get("key"):
                errors += 1
                continue

            schema_git_uid = data.get("schemaUid")
            schema_uid = git_uid_to_uid.get(schema_git_uid)
            if schema_uid is None:
                errors += 1
                continue

            key = data["key"]
            asset = db.query(Asset).filter(
                Asset.workspace_id == workspace_id, Asset.key == key
            ).first()
            is_new = asset is None
            if is_new:
                asset = Asset(uid=str(uuid.uuid4()), workspace_id=workspace_id, key=key)

            write = should_write(
                merge_strategy,
                is_new,
                None if is_new else asset.updated_at,
                _parse_git_dt(data.get("updatedAt")),
            )
            if write:
                asset.schema_uid = schema_uid
                asset.name = data.get("name") or key
                asset.type = data.get("type") or "Asset"
                asset.attributes = data.get("attributes") or {}
            db.add(asset)
            try:
                db.flush()
                assets_imported += 1
            except Exception:
                db.rollback()
                errors += 1
                continue

            asset_git_uid = data.get("uid")
            if asset_git_uid:
                asset_git_uid_to_uid[asset_git_uid] = asset.uid
            if write:
                for to_git_uid in (data.get("relations") or {}).get("outbound") or []:
                    pending_relations.append((asset_git_uid or key, to_git_uid))

            if assets_imported % 25 == 0:
                job.progress = f"Imported {assets_imported} assets"
                counts = dict(job.counts or {})
                counts["assets"] = assets_imported
                counts["errors"] = errors
                job.counts = counts
                db.commit()

        # Outbound relations reference the git-side asset uid, which is only
        # fully resolvable once every asset file has been imported.
        relations_created = 0
        if pending_relations:
            existing_relations = {
                (r.from_asset_uid, r.to_asset_uid, r.relation_type)
                for r in db.scalars(
                    select(Relation).where(Relation.workspace_id == workspace_id)
                )
            }
            for from_git_uid, to_git_uid in pending_relations:
                from_uid = asset_git_uid_to_uid.get(from_git_uid)
                to_uid = asset_git_uid_to_uid.get(to_git_uid)
                if from_uid is None or to_uid is None:
                    continue
                dedup_key = (from_uid, to_uid, "reference")
                if dedup_key in existing_relations:
                    continue
                existing_relations.add(dedup_key)
                db.add(Relation(
                    workspace_id=workspace_id,
                    from_asset_uid=from_uid,
                    to_asset_uid=to_uid,
                    relation_type="reference",
                ))
                relations_created += 1
            db.commit()

        job.status = "succeeded"
        job.progress = "Import complete"
        job.counts = {
            "schemas": schemas_imported,
            "assets": assets_imported,
            "relations": relations_created,
            "errors": errors,
        }
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
