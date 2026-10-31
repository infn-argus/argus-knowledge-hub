"""The catalogue's sources: Git repositories pinned by a lock file, read at exactly that commit
(docs/catalogue-collections.md §A).

    backend/catalogue/sources.lock.yaml

    sources:
      - id: argus
        kind: argus-collections                     # collections in this format, under collections/
        repo: https://github.com/infn-argus/argus-catalogue.git
        ref: v0.1.0                                 # a tag: it must still point at `commit`
        commit: 688a6fb…                            # the full commit: what is read
      - id: netbox
        kind: netbox-devicetype-library
        repo: https://github.com/infn-argus/devicetype-library.git
        ref: infn
        commit: 25e998f…
        select: ["Moxa/NPort-5*", "Basler/*"]        # device-types/<Manufacturer>/<file>, without .yaml
        collection: {id: it-devices, version: 0.1.0, name: …, requires: {…}}

Each repository is fetched into a bare cache (only the pinned commit) and read file by file with `git show`;
nothing is checked out, and no file of a repository is executed. A NetBox device type becomes an entry of the
collection the lock names: its id is the vendor's id and its slug without the manufacturer's prefix, its
vendor the `argus` source's vendor whose name or alias is its manufacturer, and its physical definition
(height, weight, ports, power) its specifications. What ARGUS says about it — device class, the type of its
units, end of life — comes from a `classifications` entry of the `argus` source with the same id.

The result is written once per lock (its checksum names the folder) as ordinary collection files, which
`load_tree` reads and the validator checks over both sources together.
"""
from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional

import yaml

from app.catalogue.loader import MANIFEST

LOCK = "sources.lock.yaml"
KINDS = ("argus-collections", "netbox-devicetype-library")
SHA = re.compile(r"^[0-9a-f]{40}$")


class SourceProblem(RuntimeError):
    """A source cannot be read as pinned: the person who maintains the lock can act on it."""


def lock_path(base: Optional[Path] = None) -> Path:
    from app.catalogue.loader import catalogue_dir
    return (base or catalogue_dir()) / LOCK


def cache_dir() -> Path:
    return Path(os.environ.get("ARGUS_CATALOGUE_CACHE") or "/tmp/argus-catalogue-cache")


def read_lock(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = data.get("sources") or []
    seen = set()
    for s in sources:
        for k in ("id", "kind", "repo", "commit"):
            if not s.get(k):
                raise SourceProblem(f"{path.name}: a source needs `{k}`")
        if s["kind"] not in KINDS:
            raise SourceProblem(f"{path.name}: {s['id']}: kind is one of {', '.join(KINDS)}")
        if not SHA.match(str(s["commit"])):
            raise SourceProblem(f"{path.name}: {s['id']}: `commit` is a full 40-character commit id")
        if s["id"] in seen:
            raise SourceProblem(f"{path.name}: two sources are called {s['id']!r}")
        seen.add(s["id"])
        if s["kind"] == "netbox-devicetype-library" and not (s.get("select") and s.get("collection")):
            raise SourceProblem(f"{path.name}: {s['id']}: a NetBox source needs `select` and `collection`")
    if sum(1 for s in sources if s["kind"] == "argus-collections") > 1:
        raise SourceProblem(f"{path.name}: one argus-collections source: the vendors and classifications live there")
    return sources


# --------------------------------------------------------------------------- git, read only

def _git(repo: Path, *args: str, binary: bool = False) -> Any:
    try:
        out = subprocess.run(["git", "--git-dir", str(repo), *args], capture_output=True, timeout=300, check=True,
                             env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except subprocess.CalledProcessError as e:
        raise SourceProblem(f"git {args[0]}: {e.stderr.decode(errors='replace').strip()[:300]}")
    except subprocess.TimeoutExpired:
        raise SourceProblem(f"git {args[0]}: no answer within 5 minutes")
    return out.stdout if binary else out.stdout.decode()


def fetch(source: dict, cache: Path) -> Path:
    """A bare repository holding the pinned commit. A tag (`ref`) must still point at it."""
    repo = cache / f"{source['id']}.git"
    if not repo.exists():
        repo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", "--bare", str(repo)], check=True, capture_output=True)
    commit = source["commit"]
    have = subprocess.run(["git", "--git-dir", str(repo), "cat-file", "-e", f"{commit}^{{commit}}"],
                          capture_output=True).returncode == 0
    if not have:
        _git(repo, "fetch", "-q", "--depth", "1", source["repo"], commit)
    ref = source.get("ref")
    if ref and ref.startswith("v"):                    # a release tag: it must not have moved
        lines = _git(repo, "ls-remote", source["repo"], f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}").split("\n")
        pointed = {l.split()[0] for l in lines if l.strip()}
        if pointed and commit not in pointed:
            raise SourceProblem(f"{source['id']}: the tag {ref} no longer points at the pinned commit "
                                f"{commit[:12]}: someone moved it; check the release before pinning again")
    return repo


def _files(repo: Path, commit: str, prefix: str) -> list[str]:
    return [p for p in _git(repo, "ls-tree", "-r", "--name-only", commit, "--", prefix).split("\n") if p]


def _show(repo: Path, commit: str, path: str) -> bytes:
    return _git(repo, "show", f"{commit}:{path}", binary=True)


# --------------------------------------------------------------------------- NetBox device types

def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", str(s).lower())).strip("-")


def _vendor_for(manufacturer: str, vendors: list[dict]) -> Optional[dict]:
    from app.services.catalogue_mapping import norm
    key = norm(manufacturer)
    for v in vendors:
        if key in {norm(n) for n in [v.get("name"), *(v.get("aliases") or [])] if n}:
            return v
    return None


def _count(items: Any) -> int:
    return len(items) if isinstance(items, list) else 0


def netbox_entry(doc: dict, path: str, commit: str, vendors: list[dict]) -> tuple[Optional[dict], Optional[str]]:
    """A NetBox device type as a catalogue entry (without ARGUS's classification), or why it cannot be one."""
    manufacturer, model, slug = doc.get("manufacturer"), doc.get("model"), doc.get("slug")
    if not (manufacturer and model and slug):
        return None, f"{path}: not a device type (manufacturer, model and slug)"
    vendor = _vendor_for(manufacturer, vendors)
    if vendor is None:
        return None, (f"{path}: no vendor named {manufacturer!r} (or with that alias) in the catalogue: add it to "
                      f"collections/vendors/vendors.yaml")
    prefix = _slug(manufacturer) + "-"
    rest = slug[len(prefix):] if slug.startswith(prefix) else slug
    entry: dict = {"id": f"{vendor['id']}/{rest}", "vendor": vendor["id"], "model_code": str(model),
                   "name": f"{vendor['name']} {model}"}
    if doc.get("part_number"):
        entry["part_number"] = str(doc["part_number"])
    spec: dict = {}
    if doc.get("u_height"):
        spec["rack_units"] = doc["u_height"]
        spec["full_depth"] = bool(doc.get("is_full_depth"))
    if doc.get("airflow"):
        spec["airflow"] = doc["airflow"]
    if doc.get("weight") is not None:
        spec["weight"] = {"value": doc["weight"], "unit": doc.get("weight_unit") or "kg"}
    interfaces = [i for i in doc.get("interfaces") or [] if isinstance(i, dict)]
    physical = [i for i in interfaces if i.get("type") not in ("virtual", "lag", "bridge")]
    if physical:
        spec["network_ports"] = len(physical)
        kinds: dict[str, int] = {}
        for i in physical:
            kinds[i["type"]] = kinds.get(i["type"], 0) + 1
        spec["interface_types"] = [f"{n} × {t}" if n > 1 else t for t, n in sorted(kinds.items())]
        poe = sorted({i["poe_type"] for i in physical if i.get("poe_mode") == "pd" and i.get("poe_type")})
        if poe:
            spec["poe_powered"] = poe if len(poe) > 1 else poe[0]
    for key, label in (("console-server-ports", "serial_ports"), ("console-ports", "console_ports"),
                       ("power-ports", "power_inputs"), ("power-outlets", "power_outlets")):
        if _count(doc.get(key)):
            spec[label] = _count(doc[key])
    if spec:
        entry["specifications"] = spec
    entry["sources"] = [{"kind": "netbox-devicetype-library", "ref": path, "revision": commit[:12]}]
    return entry, None


# --------------------------------------------------------------------------- the tree

def _lock_key(sources: list[dict]) -> str:
    return hashlib.sha256(yaml.safe_dump(sources, sort_keys=True).encode()).hexdigest()[:16]


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def materialize(lock: Optional[Path] = None, cache: Optional[Path] = None) -> Path:
    """The collections of every pinned source, as files in one folder (made once per lock)."""
    lock = lock or lock_path()
    cache = cache or cache_dir()
    sources = read_lock(lock)
    out = cache / f"tree-{_lock_key(sources)}"
    if (out / ".complete").exists():
        return out
    work = cache / f".building-{_lock_key(sources)}-{os.getpid()}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    try:
        argus = next((s for s in sources if s["kind"] == "argus-collections"), None)
        vendors: list[dict] = []
        classified: dict[str, dict] = {}
        if argus is not None:
            repo = fetch(argus, cache)
            for path in _files(repo, argus["commit"], "collections/"):
                if not path.endswith((".yaml", ".yml")):
                    continue
                target = work / path[len("collections/"):]
                target.parent.mkdir(parents=True, exist_ok=True)
                content = _show(repo, argus["commit"], path)
                target.write_bytes(content)
                data = yaml.safe_load(content) if not path.endswith(MANIFEST) else None
                if isinstance(data, dict):
                    vendors += [v for v in data.get("vendors") or [] if isinstance(v, dict)]
                    for c_ in data.get("classifications") or []:
                        if isinstance(c_, dict) and c_.get("id"):
                            classified[str(c_["id"])] = c_
        for s in (s for s in sources if s["kind"] == "netbox-devicetype-library"):
            repo = fetch(s, cache)
            entries, problems = [], []
            for path in _files(repo, s["commit"], "device-types/"):
                name = path[len("device-types/"):].rsplit(".", 1)[0]
                if not path.endswith((".yaml", ".yml")) or not any(fnmatch.fnmatch(name, p) for p in s["select"]):
                    continue
                doc = yaml.safe_load(_show(repo, s["commit"], path))
                entry, why = netbox_entry(doc if isinstance(doc, dict) else {}, path, s["commit"], vendors)
                if why:
                    problems.append(why)
                    continue
                meta = classified.get(entry["id"], {})
                for k in ("device_class", "instance_type", "eol_date", "typical_spares", "relations"):
                    if meta.get(k) is not None:
                        entry[k] = meta[k]
                entries.append(entry)
            if problems:
                raise SourceProblem(f"{s['id']}: " + "; ".join(problems))
            if not entries:
                raise SourceProblem(f"{s['id']}: `select` matches no device type at {s['commit'][:12]}")
            spec = s["collection"]
            d = work / spec["id"]
            d.mkdir(parents=True, exist_ok=True)
            manifest = {"id": spec["id"], "version": str(spec["version"]),
                        "name": spec.get("name") or spec["id"],
                        "description": f"Device types of {s['repo']} at {s['commit'][:12]}, read by ARGUS.",
                        "domain": spec.get("domain", "catalogue"), "owner": spec.get("owner", "INFN ARGUS"),
                        "license": spec.get("license", "CC0-1.0"), "origin": "netbox",
                        "requires": spec.get("requires") or {}, "contents": ["models.yaml"]}
            (d / MANIFEST).write_text(yaml.dump(manifest, Dumper=_Dumper, sort_keys=False))
            (d / "models.yaml").write_text(yaml.dump({"models": sorted(entries, key=lambda e: e["id"])},
                                                     Dumper=_Dumper, sort_keys=False, allow_unicode=True))
        (work / ".complete").write_text(yaml.safe_dump(sources))
        shutil.rmtree(out, ignore_errors=True)
        work.rename(out)
    except Exception:
        shutil.rmtree(work, ignore_errors=True)
        raise
    return out


def describe(lock: Optional[Path] = None) -> list[dict]:
    """The pins, as the collections page shows them."""
    path = lock or lock_path()
    if not path.is_file():
        return []
    return [{"id": s["id"], "kind": s["kind"], "repo": s["repo"], "ref": s.get("ref"), "commit": s["commit"],
             "select": s.get("select")} for s in read_lock(path)]
