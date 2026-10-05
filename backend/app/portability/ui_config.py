"""Portability set-up from the web app: repositories (GitHub, GitLab, any Git server, or a repository copied
onto this installation), the keys an import trusts, and this installation's signing key.

The deployment's own settings (ARGUS_PORTABILITY_*) stay first: what they name cannot be added, changed or
removed here, and a signing key they configure is the one used. What is registered here is added to them by
`merged()`, which every caller of `service.config()` gets.

* Switched on by default; `ARGUS_PORTABILITY_UI_CONFIG=off` switches it off. Off, nothing can be changed
  here, and what was registered before is kept in the database but not used.
* Secrets never leave the server: ARGUS makes the SSH deploy key itself and shows only its public half; a
  token is written once and never shown again. Both are stored encrypted (services/crypto.py) and written,
  decrypted, only to files in this process's temporary directory, never to a shared volume.
* An SSH server is trusted only after a person confirms its host-key fingerprints, which are then pinned.
* Under a policy with separation of duties, an addition waits for another administrator's approval. Every
  change is in the portability audit (subject kind `config`).
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.portability import PortabilityEvent
from app.models.portability_config import (PortabilityRepository, PortabilitySigningKey, PortabilityStore,
                                           PortabilityTrustedKey)
from app.portability import gitrepo, signing

NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")
SCP_LIKE = re.compile(r"^(?P<user>[\w.-]+)@(?P<host>[\w.-]+):(?P<path>[^/].*)$")
PROVIDERS = ("github", "gitlab", "other", "local")
OFF = ("0", "off", "false", "no")


class ConfigError(ValueError):
    def __init__(self, message: str, code: str = "invalid", status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status


def enabled() -> bool:
    return (os.environ.get("ARGUS_PORTABILITY_UI_CONFIG") or "on").strip().lower() not in OFF


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _runtime() -> Path:
    """Where decrypted keys and tokens are written for git and ssh: this process's own temporary directory."""
    d = Path(tempfile.gettempdir()) / f"argus-portability-web-{os.getuid()}"
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    return d


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != content:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content)
        os.chmod(tmp, 0o600)
        tmp.replace(path)
    return path


def _encrypt(plain: str) -> str:
    from app.services.crypto import encrypt_secret
    return encrypt_secret(plain)


def _decrypt(token: str) -> str:
    from app.services.crypto import decrypt_secret
    return decrypt_secret(token)


def _audit(db: Session, kind: str, subject: str, actor: str, detail: Optional[dict] = None) -> None:
    db.add(PortabilityEvent(subject_kind="config", subject_id=subject, kind=kind, actor=actor, detail=detail or {}))


def _initial_status(cfg) -> str:
    return "pending" if cfg.policy.separation_of_duties else "active"


def _require(cfg) -> None:
    if not enabled():
        raise ConfigError("setting up portability from the web app is switched off on this installation "
                          "(ARGUS_PORTABILITY_UI_CONFIG): it is done in the deployment's settings", "ui_config_off", 403)


# ------------------------------------------------------------------------------------------- addresses

def parse_url(url: str, root: Path) -> dict:
    """{auth, host, port, provider} for an address ARGUS may use, or a ConfigError saying why not."""
    url = (url or "").strip()
    if not url:
        raise ConfigError("give the repository's address")
    if url.startswith("/"):
        path = Path(url).resolve()
        if root.resolve() not in (path, *path.parents):
            raise ConfigError(f"a repository on this installation must be inside the portability area ({root})")
        return {"auth": "local", "host": None, "port": None, "provider": "local"}
    scp = SCP_LIKE.match(url)
    if scp:
        host, port = scp["host"], 22
    else:
        parts = urlsplit(url)
        if parts.scheme == "https":
            if parts.password:
                raise ConfigError("do not put a password or token in the address: give the token separately")
            host, port = parts.hostname or "", parts.port or 443
            return {"auth": "https", "host": host, "port": port, "provider": _provider(host)}
        if parts.scheme != "ssh":
            raise ConfigError("use an ssh://, git@host:path or https:// address (or a path on this installation)")
        host, port = parts.hostname or "", parts.port or 22
    if not host:
        raise ConfigError("the address names no server")
    return {"auth": "ssh", "host": host, "port": port, "provider": _provider(host)}


def _provider(host: str) -> str:
    host = host.lower()
    return "github" if "github" in host else "gitlab" if "gitlab" in host or host.startswith("baltig.") else "other"


# ------------------------------------------------------------------------------------------- host keys

def _fingerprint(blob_b64: str) -> str:
    return "SHA256:" + base64.b64encode(hashlib.sha256(base64.b64decode(blob_b64)).digest()).decode().rstrip("=")


def scan_host_keys(host: str, port: int) -> list[dict]:
    """The server's host keys, as ssh-keyscan reports them: for a person to compare with the fingerprints
    the provider publishes before they are pinned."""
    r = subprocess.run(["ssh-keyscan", "-T", "10", "-p", str(port), "-t", "ed25519,ecdsa,rsa", host],
                       capture_output=True, text=True, timeout=30)
    keys = []
    for line in r.stdout.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 3:
            keys.append({"line": line.strip(), "type": parts[1], "fingerprint": _fingerprint(parts[2])})
    if not keys:
        raise ConfigError(f"could not read {host}'s host keys on port {port}: "
                          f"{(r.stderr or 'no answer').strip()[:200]}", "host_unreachable", 502)
    return keys


# ------------------------------------------------------------------------------------------- views

def _repo_view(r: PortabilityRepository) -> dict:
    usable = r.status == "active" and (r.auth != "ssh" or r.host_keys_confirmed)
    return {"name": r.name, "url": r.url, "provider": r.provider, "auth": r.auth, "source": "web",
            "public_key": r.public_key, "has_token": bool(r.encrypted_token),
            "host_keys": [{"type": k["type"], "fingerprint": k["fingerprint"]} for k in (r.host_keys or [])],
            "host_keys_confirmed": r.host_keys_confirmed, "status": r.status, "usable": usable,
            "created_by": r.created_by, "created_at": r.created_at, "approved_by": r.approved_by,
            "last_test": r.last_test}


def view(db: Session, cfg) -> dict:
    """What the Portability page shows: the deployment's set-up (names only) and what was registered here."""
    trusted = list(db.scalars(select(PortabilityTrustedKey).order_by(PortabilityTrustedKey.created_at)))
    keys = list(db.scalars(select(PortabilitySigningKey).where(PortabilitySigningKey.status != "retired")
                           .order_by(PortabilitySigningKey.created_at)))
    deployment = (cfg.sources or {}).get("deployment", {})
    stores = list(db.scalars(select(PortabilityStore).order_by(PortabilityStore.name)))
    return {
        "enabled": enabled(),
        "separation_of_duties": bool(cfg.policy.separation_of_duties),
        "deployment": {"repositories": sorted(deployment.get("repositories", [])),
                       "stores": sorted(deployment.get("stores", [])),
                       "signing_key": bool(deployment.get("signing_key")),
                       "trusted_keys": bool(deployment.get("trusted_keys"))},
        "repositories": [_repo_view(r) for r in db.scalars(select(PortabilityRepository)
                                                           .order_by(PortabilityRepository.name))],
        "trusted_keys": [{"id": k.id, "principal": k.principal, "key_id": k.key_id, "note": k.note,
                          "line": k.line, "status": k.status, "created_by": k.created_by,
                          "created_at": k.created_at, "approved_by": k.approved_by} for k in trusted],
        "stores": [{"name": x.name, "note": x.note, "status": x.status, "path": str(cfg.root / "stores" / x.name),
                    "created_by": x.created_by, "created_at": x.created_at, "approved_by": x.approved_by}
                   for x in stores],
        "signing_keys": [{"id": k.id, "principal": k.principal, "key_id": k.key_id, "public_line": k.public_line,
                          "status": k.status, "created_by": k.created_by, "created_at": k.created_at,
                          "approved_by": k.approved_by} for k in keys],
    }


# ------------------------------------------------------------------------------------------- repositories

def add_repository(db: Session, cfg, actor: str, *, name: str, url: str, provider: Optional[str] = None,
                   token: Optional[str] = None) -> dict:
    _require(cfg)
    name = (name or "").strip().lower()
    if not NAME.match(name):
        raise ConfigError("a name is 2–41 lower-case letters, digits, - or _, starting with a letter or digit")
    if name in (cfg.sources or {}).get("deployment", {}).get("repositories", []):
        raise ConfigError(f"{name!r} is set by the deployment and cannot be registered here", "deployment", 409)
    if db.get(PortabilityRepository, name) is not None:
        raise ConfigError(f"a repository named {name!r} is already registered", "exists", 409)
    where = parse_url(url, cfg.root)
    auth = where["auth"]
    if auth == "https" and not (token or "").strip():
        auth = "none"                       # a public repository: read without credentials
    if auth == "local" and token:
        raise ConfigError("a repository on this installation takes no token")
    repo = PortabilityRepository(name=name, url=url.strip(), provider=provider if provider in PROVIDERS else
                                 where["provider"], auth=auth, status=_initial_status(cfg), created_by=actor)
    if auth == "ssh":
        key = Ed25519PrivateKey.generate()
        repo.encrypted_private_key = _encrypt(key.private_bytes(serialization.Encoding.PEM,
                                                                serialization.PrivateFormat.OpenSSH,
                                                                serialization.NoEncryption()).decode())
        instance = os.environ.get("ARGUS_INSTANCE_NAME", "argus")
        repo.public_key = key.public_key().public_bytes(serialization.Encoding.OpenSSH,
                                                        serialization.PublicFormat.OpenSSH).decode() + \
            f" argus-{instance}-{name}"
        try:
            repo.host_keys = scan_host_keys(where["host"], where["port"])
        except ConfigError:
            repo.host_keys = []             # shown as unreachable; read them again from the page
    elif auth == "https":
        repo.encrypted_token = _encrypt(token.strip())
    db.add(repo)
    _audit(db, "repository_added", f"repository:{name}", actor,
           {"url": repo.url, "auth": auth, "provider": repo.provider, "status": repo.status})
    db.flush()
    return _repo_view(repo)


def _repo(db: Session, name: str) -> PortabilityRepository:
    repo = db.get(PortabilityRepository, name)
    if repo is None:
        raise ConfigError(f"no repository {name!r} is registered here", "not_found", 404)
    return repo


def update_repository(db: Session, cfg, actor: str, name: str, *, url: Optional[str] = None,
                      provider: Optional[str] = None) -> dict:
    """Change a registered repository's address or provider. The kind of access stays (SSH, HTTPS, or on this
    installation): to change it, remove and register again. A new SSH server must be confirmed again, and
    under separation of duties the change waits for another administrator."""
    _require(cfg)
    repo = _repo(db, name)
    before = {"url": repo.url, "provider": repo.provider}
    if url is not None and url.strip() and url.strip() != repo.url:
        where = parse_url(url, cfg.root)
        family = {"ssh": "ssh", "https": "https", "none": "https", "local": "local"}
        if family[where["auth"]] != family[repo.auth]:
            raise ConfigError("the address changes the kind of access (SSH, HTTPS or on this installation): "
                              "remove the repository and register it again")
        old = parse_url(repo.url, cfg.root)
        repo.url = url.strip()
        if repo.auth == "ssh" and (where["host"], where["port"]) != (old["host"], old["port"]):
            repo.host_keys_confirmed = False
            try:
                repo.host_keys = scan_host_keys(where["host"], where["port"])
            except ConfigError:
                repo.host_keys = []
        repo.status = _initial_status(cfg)
        repo.approved_by = repo.approved_at = None
    if provider is not None and provider in PROVIDERS:
        repo.provider = provider
    if {"url": repo.url, "provider": repo.provider} != before:
        _audit(db, "repository_changed", f"repository:{name}", actor,
               {"before": before, "after": {"url": repo.url, "provider": repo.provider}, "status": repo.status})
    db.flush()
    return _repo_view(repo)


def rescan_host_keys(db: Session, cfg, actor: str, name: str) -> dict:
    _require(cfg)
    repo = _repo(db, name)
    if repo.auth != "ssh":
        raise ConfigError("only an SSH repository has host keys")
    where = parse_url(repo.url, cfg.root)
    repo.host_keys, repo.host_keys_confirmed = scan_host_keys(where["host"], where["port"]), False
    _audit(db, "host_keys_read", f"repository:{name}", actor,
           {"fingerprints": [k["fingerprint"] for k in repo.host_keys]})
    db.flush()
    return _repo_view(repo)


def confirm_host_keys(db: Session, cfg, actor: str, name: str, fingerprints: list[str]) -> dict:
    """Pin the server's host keys: the person confirms exactly the fingerprints they were shown, so a key
    that changed in between is not pinned unseen."""
    _require(cfg)
    repo = _repo(db, name)
    shown = {k["fingerprint"] for k in repo.host_keys or []}
    if not shown:
        raise ConfigError("the server's host keys have not been read yet")
    if set(fingerprints or []) != shown:
        raise ConfigError("the fingerprints confirmed are not the ones read from the server: read them again",
                          "host_keys_changed", 409)
    repo.host_keys_confirmed = True
    _audit(db, "host_keys_confirmed", f"repository:{name}", actor, {"fingerprints": sorted(shown)})
    db.flush()
    return _repo_view(repo)


def set_token(db: Session, cfg, actor: str, name: str, token: str) -> dict:
    _require(cfg)
    repo = _repo(db, name)
    if repo.auth not in ("https", "none") or not (token or "").strip():
        raise ConfigError("a token is given to an https repository, and cannot be empty")
    repo.encrypted_token, repo.auth = _encrypt(token.strip()), "https"
    _audit(db, "token_replaced", f"repository:{name}", actor)
    db.flush()
    return _repo_view(repo)


def remove_repository(db: Session, cfg, actor: str, name: str) -> None:
    _require(cfg)
    repo = _repo(db, name)
    _audit(db, "repository_removed", f"repository:{name}", actor, {"url": repo.url})
    db.delete(repo)
    db.flush()


def _materialize_repo(repo: PortabilityRepository, base: Path) -> dict:
    """{key, token, known_hosts} files for one repository's credentials."""
    out: dict = {}
    if repo.encrypted_private_key:
        out["key"] = _write(base / "keys" / repo.name, _decrypt(repo.encrypted_private_key))
    if repo.encrypted_token:
        out["token"] = _write(base / "tokens" / repo.name, _decrypt(repo.encrypted_token))
    if repo.host_keys and repo.host_keys_confirmed:
        out["known_hosts"] = _write(base / "known_hosts" / repo.name,
                                    "".join(k["line"] + "\n" for k in repo.host_keys))
    return out


def test_repository(db: Session, cfg, actor: str, name: str, write: bool = False) -> dict:
    """Can ARGUS reach it: read (`git ls-remote`), and with `write` push a branch `argus-connection-test`
    and delete it again. Usable before approval, so a person can check what they registered."""
    _require(cfg)
    repo = _repo(db, name)
    if repo.auth == "ssh" and not repo.host_keys_confirmed:
        raise ConfigError("confirm the server's host keys first")
    files = _materialize_repo(repo, _runtime() / "test")
    env = gitrepo.credentials_env(files.get("key"), files.get("token"), _runtime() / "askpass",
                                  known_hosts=files.get("known_hosts"))
    result: dict = {"at": _now().isoformat(), "read": False, "write": None, "error": None}
    work = Path(tempfile.mkdtemp(prefix="argus-repo-test-"))
    try:
        r = gitrepo.git(["ls-remote", repo.url], cwd=work, check=False, env=env)
        result["read"] = r.returncode == 0
        if not result["read"]:
            result["error"] = (r.stderr or "").strip()[:300]
        elif write:
            gitrepo.git(["init", "-q", "-b", "argus-connection-test", "."], cwd=work)
            (work / "README").write_text("ARGUS connection test; deleted at once.\n")
            gitrepo.git(["add", "README"], cwd=work)
            gitrepo.git(["-c", "user.name=ARGUS", "-c", "user.email=argus@localhost", "commit", "-q", "-m",
                         "ARGUS connection test"], cwd=work)
            pushed = gitrepo.git(["push", "-q", repo.url, "HEAD:refs/heads/argus-connection-test"], cwd=work,
                                 check=False, env=env)
            result["write"] = pushed.returncode == 0
            if pushed.returncode == 0:
                gitrepo.git(["push", "-q", repo.url, "--delete", "argus-connection-test"], cwd=work, check=False,
                            env=env)
            else:
                result["error"] = (pushed.stderr or "").strip()[:300]
    finally:
        shutil.rmtree(work, ignore_errors=True)
        shutil.rmtree(_runtime() / "test", ignore_errors=True)
    repo.last_test = result
    _audit(db, "repository_tested", f"repository:{name}", actor,
           {k: result[k] for k in ("read", "write")} | ({"error": result["error"]} if result["error"] else {}))
    db.flush()
    return _repo_view(repo)


# ------------------------------------------------------------------------------------------- keys

def _parse_allowed_signer(line: str) -> tuple[str, str, str]:
    """(principal, normalized allowed-signers line, key id) for one line another installation gave."""
    parts = (line or "").strip().split()
    if "ssh-ed25519" not in parts or parts.index("ssh-ed25519") == 0 or parts.index("ssh-ed25519") + 1 >= len(parts):
        raise ConfigError("paste the other installation's allowed-signers line: "
                          "<principal> [namespaces=\"…\"] ssh-ed25519 AAAA…")
    i = parts.index("ssh-ed25519")
    principal, blob = parts[0], parts[i + 1]
    try:
        key = serialization.load_ssh_public_key(f"ssh-ed25519 {blob}".encode())
    except (ValueError, TypeError) as e:
        raise ConfigError(f"that is not a valid Ed25519 public key ({e})") from e
    if not isinstance(key, Ed25519PublicKey):
        raise ConfigError("only Ed25519 keys sign ARGUS archives")
    normalized = f'{principal} namespaces="git,{signing.NAMESPACE}" ssh-ed25519 {blob}'
    return principal, normalized, signing.key_id(key)


def add_trusted_key(db: Session, cfg, actor: str, line: str, note: Optional[str] = None) -> dict:
    _require(cfg)
    principal, normalized, kid = _parse_allowed_signer(line)
    if db.scalar(select(PortabilityTrustedKey).where(PortabilityTrustedKey.key_id == kid)) is not None:
        raise ConfigError("that key is already trusted here", "exists", 409)
    k = PortabilityTrustedKey(id=str(uuid.uuid4()), principal=principal, line=normalized, key_id=kid,
                              note=(note or "").strip()[:200] or None, status=_initial_status(cfg), created_by=actor)
    db.add(k)
    _audit(db, "trusted_key_added", f"trusted:{kid}", actor, {"principal": principal, "status": k.status})
    db.flush()
    return {"id": k.id, "principal": principal, "key_id": kid, "status": k.status}


def update_trusted_key(db: Session, cfg, actor: str, key_id: str, note: Optional[str]) -> dict:
    """The note on a trusted key (which installation it is). The key itself never changes: trust a new one."""
    _require(cfg)
    k = db.get(PortabilityTrustedKey, key_id)
    if k is None:
        raise ConfigError("no such trusted key", "not_found", 404)
    k.note = (note or "").strip()[:200] or None
    _audit(db, "trusted_key_noted", f"trusted:{k.key_id}", actor, {"note": k.note})
    db.flush()
    return {"id": k.id, "note": k.note}


# ------------------------------------------------------------------------------------------- artifact stores

def add_store(db: Session, cfg, actor: str, name: str, note: Optional[str] = None) -> dict:
    """An artifact store: a directory in the portability area, <root>/stores/<name>, on the same volume."""
    _require(cfg)
    name = (name or "").strip().lower()
    if not NAME.match(name):
        raise ConfigError("a name is 2–41 lower-case letters, digits, - or _, starting with a letter or digit")
    if name in (cfg.sources or {}).get("deployment", {}).get("stores", []):
        raise ConfigError(f"{name!r} is set by the deployment", "deployment", 409)
    if db.get(PortabilityStore, name) is not None:
        raise ConfigError(f"a store named {name!r} is already registered", "exists", 409)
    store = PortabilityStore(name=name, note=(note or "").strip()[:200] or None, status=_initial_status(cfg),
                             created_by=actor)
    db.add(store)
    (cfg.root / "stores" / name).mkdir(parents=True, exist_ok=True)
    _audit(db, "store_added", f"store:{name}", actor, {"status": store.status})
    db.flush()
    return {"name": name, "status": store.status, "path": str(cfg.root / "stores" / name)}


def remove_store(db: Session, cfg, actor: str, name: str) -> None:
    """Unregister a store. Its files stay on the volume: exports that used it still need them."""
    _require(cfg)
    store = db.get(PortabilityStore, name)
    if store is None:
        raise ConfigError(f"no store {name!r} is registered here", "not_found", 404)
    _audit(db, "store_removed", f"store:{name}", actor)
    db.delete(store)
    db.flush()


def remove_trusted_key(db: Session, cfg, actor: str, key_id: str) -> None:
    _require(cfg)
    k = db.get(PortabilityTrustedKey, key_id)
    if k is None:
        raise ConfigError("no such trusted key", "not_found", 404)
    _audit(db, "trusted_key_removed", f"trusted:{k.key_id}", actor, {"principal": k.principal})
    db.delete(k)
    db.flush()


def generate_signing_key(db: Session, cfg, actor: str, principal: Optional[str] = None) -> dict:
    """This installation's signing key, made here. Refused when the deployment configures one. A new key
    replaces the previous one once it is active; give its public line to every installation that imports
    from this one."""
    _require(cfg)
    if (cfg.sources or {}).get("deployment", {}).get("signing_key"):
        raise ConfigError("the deployment configures this installation's signing key", "deployment", 409)
    principal = (principal or os.environ.get("ARGUS_INSTANCE_NAME") or "argus-portability").strip()
    if not re.match(r"^[\w.@-]{2,64}$", principal):
        raise ConfigError("the principal is a short name such as argus-infn")
    key = Ed25519PrivateKey.generate()
    public = key.public_key()
    line = (f'{principal} namespaces="git,{signing.NAMESPACE}" '
            + public.public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH).decode())
    k = PortabilitySigningKey(id=str(uuid.uuid4()), principal=principal, public_line=line,
                              key_id=signing.key_id(public), status=_initial_status(cfg), created_by=actor,
                              encrypted_private_key=_encrypt(key.private_bytes(
                                  serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
                                  serialization.NoEncryption()).decode()))
    db.add(k)
    if k.status == "active":
        _retire_other_signing_keys(db, k, actor)
    _audit(db, "signing_key_generated", f"signing:{k.key_id}", actor, {"principal": principal, "status": k.status})
    db.flush()
    return {"id": k.id, "principal": principal, "key_id": k.key_id, "public_line": line, "status": k.status}


def _retire_other_signing_keys(db: Session, keep: PortabilitySigningKey, actor: str) -> None:
    for other in db.scalars(select(PortabilitySigningKey).where(PortabilitySigningKey.status == "active",
                                                               PortabilitySigningKey.id != keep.id)):
        other.status, other.retired_at = "retired", _now()
        _audit(db, "signing_key_retired", f"signing:{other.key_id}", actor, {"replaced_by": keep.key_id})


# ------------------------------------------------------------------------------------------- approval

def approve(db: Session, cfg, actor: str, kind: str, ident: str) -> dict:
    """Another administrator activates what someone registered (policies with separation of duties)."""
    _require(cfg)
    model = {"repository": PortabilityRepository, "trusted_key": PortabilityTrustedKey,
             "signing_key": PortabilitySigningKey, "store": PortabilityStore}.get(kind)
    if model is None:
        raise ConfigError("approve a repository, a trusted_key or a signing_key")
    row = db.get(model, ident)
    if row is None:
        raise ConfigError("nothing to approve by that id", "not_found", 404)
    if row.status != "pending":
        raise ConfigError("it is not waiting for approval", "not_pending", 409)
    if row.created_by == actor:
        raise ConfigError("another administrator must approve what you registered", "separation_of_duties", 403)
    row.status, row.approved_by, row.approved_at = "active", actor, _now()
    if isinstance(row, PortabilitySigningKey):
        _retire_other_signing_keys(db, row, actor)
    subject = (f"repository:{row.name}" if kind == "repository" else f"store:{row.name}" if kind == "store"
               else f"{kind.split('_')[0]}:{row.key_id}")
    _audit(db, "approved", subject, actor, {"kind": kind})
    db.flush()
    return {"kind": kind, "id": ident, "status": row.status}


# ------------------------------------------------------------------------------------------- merging

def merged(cfg):
    """The deployment's configuration with the web app's set-up added: repositories it does not name, a
    signing key when it configures none, and trusted keys next to its own."""
    deployment = {"repositories": sorted(cfg.repositories), "stores": sorted(cfg.stores),
                  "signing_key": cfg.signer is not None,
                  "trusted_keys": cfg.trusted is not None}
    cfg.sources = {"deployment": deployment,
                   "repositories": {name: "deployment" for name in cfg.repositories}}
    if not enabled():
        return cfg
    from app.db import SessionLocal
    try:
        with SessionLocal() as db:
            repos = list(db.scalars(select(PortabilityRepository).where(PortabilityRepository.status == "active")))
            stores = list(db.scalars(select(PortabilityStore).where(PortabilityStore.status == "active")))
            trusted = list(db.scalars(select(PortabilityTrustedKey).where(PortabilityTrustedKey.status == "active")))
            signer_row = db.scalar(select(PortabilitySigningKey).where(PortabilitySigningKey.status == "active")
                                   .order_by(PortabilitySigningKey.created_at.desc()).limit(1))
    except Exception:  # noqa: BLE001 — before the tables exist (an older database), the deployment's set-up stands
        return cfg
    from app.portability.artifacts import DirectoryStore
    for store in stores:
        if store.name not in cfg.stores:
            cfg.stores[store.name] = DirectoryStore(store.name, cfg.root / "stores" / store.name)
            cfg.sources.setdefault("stores", {})[store.name] = "web"
    base = _runtime()
    for repo in repos:
        if repo.name in cfg.repositories or (repo.auth == "ssh" and not repo.host_keys_confirmed):
            continue
        files = _materialize_repo(repo, base)
        cfg.repositories[repo.name] = repo.url
        if "key" in files:
            cfg.repository_keys[repo.name] = files["key"]
        if "token" in files:
            cfg.repository_tokens[repo.name] = files["token"]
        if "known_hosts" in files:
            cfg.repository_known_hosts[repo.name] = files["known_hosts"]
        cfg.sources["repositories"][repo.name] = "web"
    lines = []
    if cfg.signer is None and signer_row is not None:
        path = _write(base / "signing_key", _decrypt(signer_row.encrypted_private_key))
        cfg.signer = signing.Signer(path, signer_row.principal)
        cfg.sources["signing_key"] = "web"
        lines.append(signer_row.public_line)        # its own archives verify here too
    lines += [k.line for k in trusted]
    if lines:
        own = cfg.trusted.read_text() if cfg.trusted is not None and cfg.trusted.exists() else ""
        cfg.trusted = _write(base / "allowed_signers", own + ("" if own.endswith("\n") or not own else "\n")
                             + "".join(line.rstrip("\n") + "\n" for line in lines))
        cfg.sources["trusted_keys"] = "both" if own else "web"
    return cfg
