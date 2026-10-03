"""Content-addressed artifacts: attachments, source-revision contents and other blobs travel outside
Git, named by their SHA-256.

    sha256:<digest>  →  <store>/sha256/<aa>/<digest>

The Git repository holds only `blobs.manifest.ndjson`: digest, size, MIME type, classification,
encryption, retention class, locator and the recipients a decryption needs. Cloning the repository
and fetching every locator it names is enough to verify and rebuild the checkpoint.

Implemented: a directory store (a mounted institutional volume, or the staging area an operator
syncs to S3 or an OCI registry). Designed, not built: S3-compatible and OCI-artifact stores, and
per-recipient encryption (docs/export-import-design.md §7).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from app.portability.chunks import LIMITS


class ArtifactError(ValueError):
    pass


class DirectoryStore:
    scheme = "argus-artifacts"

    def __init__(self, name: str, root: Path):
        if not name.replace("-", "").replace("_", "").isalnum():
            raise ArtifactError(f"artifact store name {name!r}: letters, digits, - and _ only")
        self.name, self.root = name, Path(root)

    def _path(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ArtifactError(f"not a SHA-256 digest: {digest!r}")
        return self.root / "sha256" / digest[:2] / digest

    def locator(self, digest: str) -> str:
        return f"{self.scheme}://{self.name}/sha256/{digest}"

    def has(self, digest: str) -> bool:
        return self._path(digest).is_file()

    def put_file(self, src: Path) -> tuple[str, int]:
        """Copy a file in, by its digest. Immutable: an existing digest is never rewritten."""
        h = hashlib.sha256()
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root)
        size = 0
        with os.fdopen(fd, "wb") as out, open(src, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
                out.write(block)
                size += len(block)
        digest = h.hexdigest()
        return self._commit(Path(tmp), digest), size

    def put_bytes(self, data: bytes) -> tuple[str, int]:
        digest = hashlib.sha256(data).hexdigest()
        if not self.has(digest):
            self.root.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.root)
            with os.fdopen(fd, "wb") as out:
                out.write(data)
            self._commit(Path(tmp), digest)
        return digest, len(data)

    def _commit(self, tmp: Path, digest: str) -> str:
        final = self._path(digest)
        if final.exists():
            tmp.unlink()
        else:
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, final)
            os.chmod(final, 0o444)
        return digest

    def fetch(self, digest: str, size: Optional[int], dest: Path) -> None:
        """Copy an artifact into quarantine and prove it is what the manifest says."""
        src = self._path(digest)
        if not src.is_file():
            raise ArtifactError(f"artifact sha256:{digest} is missing from {self.name}")
        actual = src.stat().st_size
        if actual > LIMITS.max_blob_bytes or (size is not None and actual != size):
            raise ArtifactError(f"artifact sha256:{digest}: {actual} bytes, the manifest says {size}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        got = hashlib.sha256(dest.read_bytes()).hexdigest() if actual < (64 << 20) else _hash_file(dest)
        if got != digest:
            dest.unlink()
            raise ArtifactError(f"artifact sha256:{digest} does not match its content")


def _hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def resolve(locator: str, stores: dict[str, DirectoryStore]) -> tuple[DirectoryStore, str]:
    prefix = f"{DirectoryStore.scheme}://"
    if not locator.startswith(prefix):
        raise ArtifactError(f"unsupported artifact locator {locator!r} (only {prefix}… is implemented)")
    name, _, rest = locator[len(prefix):].partition("/")
    if name not in stores:
        raise ArtifactError(f"artifact store {name!r} is not configured here")
    if not rest.startswith("sha256/"):
        raise ArtifactError(f"malformed locator {locator!r}")
    return stores[name], rest[len("sha256/"):]


def configured_stores() -> dict[str, DirectoryStore]:
    """`ARGUS_PORTABILITY_ARTIFACT_STORES=name=/path,other=/path`."""
    out = {}
    for item in filter(None, (os.environ.get("ARGUS_PORTABILITY_ARTIFACT_STORES") or "").split(",")):
        name, _, path = item.partition("=")
        out[name.strip()] = DirectoryStore(name.strip(), Path(path.strip()))
    return out
