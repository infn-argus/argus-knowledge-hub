"""Verify a checkpoint in quarantine: every file, every chunk, every blob, the signature.

Independent of Git and of the database: the same checks run on a checkpoint fetched from the
portability repository, uploaded by hand, or read straight from an escrow copy.

1. The signature: over the checksums file and the manifest, by a trusted key.
2. The manifest: required fields, capabilities, the watermark vector and its hash, the sequenced
   families this importer knows.
3. Chunks: those stored in Git are present; those stored as artifacts are fetched by locator into
   quarantine. Every file must match the signed checksums (encrypted bytes, for an encrypted export).
4. Content: each chunk decompressed within limits and checked against its rows and content hash —
   after decryption, into a separate plaintext area, when the export is encrypted.
5. Blobs: each fetched by locator, checked by its stored digest, decrypted when encrypted, checked by
   its content digest.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional

from app.portability import FORMAT, FORMAT_MAJOR, chunks, envelope
from app.portability.artifacts import ArtifactError, DirectoryStore, resolve
from app.portability.families import BY_NAME, SEQUENCED_TABLES
from app.portability.signing import SignatureError, trusted_keys, verify_checkpoint

REQUIRED = ("format", "format_major", "export_id", "mode", "labels", "argus", "workspaces", "watermark", "identity",
            "families", "blobs", "classifications", "closure", "importer")
SUPPORTED_CAPABILITIES = {"argus-archive/1", "zstd", "ed25519", "ledger-replay/1", "watermark-vector/1",
                          "external-chunks/1", "envelope/1"}
# Deterministic format migrations, by major version: none yet (argus-archive/1 is the first).
MIGRATIONS: dict = {}


class VerificationError(ValueError):
    def __init__(self, message: str, code: str, detail: Optional[dict] = None):
        super().__init__(message)
        self.code, self.detail = code, detail or {}


def _vector_sha(vector: dict) -> str:
    return hashlib.sha256(json.dumps({k: int(v) for k, v in sorted(vector.items())}, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def verify(checkpoint: Path, *, trusted: Optional[Path] = None, stores: Optional[dict[str, DirectoryStore]] = None,
           blob_dir: Optional[Path] = None, lfs: Optional[list] = None, limits: chunks.Limits = chunks.LIMITS,
           require_signature: bool = True, private_keys: Optional[list] = None,
           plain_dir: Optional[Path] = None) -> dict:
    """{"report", "manifest", "plain"}: `plain` is where readable chunks are (the checkpoint itself, or
    the decrypted copy). Raises VerificationError at the first thing that fails."""
    report: dict = {"files": 0, "chunks": 0, "rows": 0, "blobs": 0, "blob_bytes": 0, "signed_by": None,
                    "external_chunks": 0, "content_verified": False}
    sums_path = checkpoint / "checksums.sha256"
    if not sums_path.exists():
        raise VerificationError("the checkpoint has no checksums.sha256", "missing_chunk")
    sums_text = sums_path.read_text()
    listed: dict[str, str] = {}
    for raw in sums_text.splitlines():
        digest, _, name = raw.partition("  ")
        if len(digest) != 64 or not name or "/" in name or name in listed:
            raise VerificationError(f"malformed checksums line {raw[:80]!r}", "malformed")
        listed[name] = digest
    if "manifest.json" not in listed or not (checkpoint / "manifest.json").exists():
        raise VerificationError("the checkpoint has no manifest", "missing_chunk")
    manifest_body = (checkpoint / "manifest.json").read_bytes()
    manifest_sha = hashlib.sha256(manifest_body).hexdigest()
    if manifest_sha != listed["manifest.json"]:
        raise VerificationError("manifest.json does not match its checksum", "checksum_mismatch")
    sig_path = checkpoint / "signature.json"
    if sig_path.exists():
        try:
            report["signed_by"] = verify_checkpoint(json.loads(sig_path.read_text()),
                                                    hashlib.sha256(sums_text.encode()).hexdigest(), manifest_sha,
                                                    trusted_keys(trusted))
        except (SignatureError, ValueError) as e:
            raise VerificationError(str(e), "bad_signature") from e
    elif require_signature:
        raise VerificationError("the checkpoint is not signed", "unsigned")
    try:
        manifest = json.loads(manifest_body)
    except ValueError as e:
        raise VerificationError(f"manifest.json is not JSON ({e})", "malformed") from e
    manifest = migrate(manifest)
    missing = [k for k in REQUIRED if k not in manifest]
    if missing:
        raise VerificationError(f"the manifest lacks {missing}", "malformed")
    if not set(manifest["importer"].get("requires", [])) <= SUPPORTED_CAPABILITIES:
        raise VerificationError(f"this importer lacks {sorted(set(manifest['importer']['requires']) - SUPPORTED_CAPABILITIES)}",
                                "incompatible")
    wm = manifest["watermark"]
    if set(wm.get("vector", {})) != set(SEQUENCED_TABLES):
        raise VerificationError("the watermark vector names other sequenced families than this importer knows",
                                "incompatible")
    if _vector_sha(wm["vector"]) != wm.get("vector_sha256"):
        raise VerificationError("the watermark vector does not match its hash", "malformed")
    if manifest.get("base") and _vector_sha(manifest["base"]["watermark"]["vector"]) != \
            manifest["base"]["watermark"].get("vector_sha256"):
        raise VerificationError("the base watermark vector does not match its hash", "malformed")

    # Chunks that live as artifacts come into quarantine first.
    for fname, fam in manifest["families"].items():
        for c in fam["chunks"]:
            if c.get("storage") == "artifact" and not (checkpoint / c["file"]).exists():
                try:
                    store, digest = resolve(c["locator"], stores or {})
                    if digest != c["sha256"] or listed.get(c["file"]) != digest:
                        raise ArtifactError(f"chunk {c['file']}: locator, manifest and checksums disagree")
                    store.fetch(digest, c["bytes"], checkpoint / c["file"])
                except ArtifactError as e:
                    raise VerificationError(str(e), "missing_chunk") from e
                report["external_chunks"] += 1
    present = {p.name for p in checkpoint.iterdir() if p.is_file()} - {"checksums.sha256", "signature.json"}
    if present - set(listed):
        raise VerificationError(f"files not covered by the checksums: {sorted(present - set(listed))[:10]}",
                                "unlisted_file")
    lfs_files = {x["file"]: x for x in (lfs or [])}
    for name, digest in listed.items():
        path = checkpoint / name
        if name in lfs_files:
            _resolve_lfs(path, lfs_files[name], stores or {})
        if not path.exists():
            raise VerificationError(f"{name} is listed but missing", "missing_chunk")
        if path.stat().st_size > limits.max_file_bytes:
            raise VerificationError(f"{name} is over the size limit", "too_large")
        if chunks.sha256_file(path) != digest:
            raise VerificationError(f"{name} does not match its checksum", "checksum_mismatch")
        report["files"] += 1

    # Content: decrypted first when the export is encrypted.
    enc = manifest.get("encryption")
    dek = None
    plain = checkpoint
    if enc:
        if not private_keys:
            report["content_verified"] = False
            report["encrypted"] = True
            return {"report": report, "manifest": manifest, "plain": None}
        try:
            dek = envelope.unwrap(enc, private_keys)
        except envelope.EnvelopeError as e:
            raise VerificationError(str(e), "decryption_failed") from e
        plain = plain_dir or (checkpoint.parent / "plain")
        plain.mkdir(parents=True, exist_ok=True)
        for fam in manifest["families"].values():
            for c in fam["chunks"]:
                _decrypt_to(checkpoint / c["file"], plain / c["file"], dek, c["file"])
        _decrypt_to(checkpoint / manifest["blobs"]["manifest"], plain / manifest["blobs"]["manifest"], dek,
                    "blobs.manifest.ndjson")
    for fname, fam in manifest["families"].items():
        if fname not in BY_NAME:
            raise VerificationError(f"unknown family {fname!r}", "incompatible")
        h = hashlib.sha256()
        rows = 0
        for c in fam["chunks"]:
            if c["file"] not in listed:
                raise VerificationError(f"chunk {c['file']} is not in the checksums", "missing_chunk")
            n, content = chunks.content_sha256(plain / c["file"], fname, limits)
            if n != c["rows"] or content != c["content_sha256"]:
                raise VerificationError(f"chunk {c['file']} holds other rows than the manifest says",
                                        "checksum_mismatch")
            h.update(content.encode())
            rows += n
            report["chunks"] += 1
        if rows != fam["rows"] or h.hexdigest() != fam["sha256"]:
            raise VerificationError(f"family {fname}: counts or hash differ from the manifest", "checksum_mismatch")
        report["rows"] += rows
    report["content_verified"] = True

    blobs_path = plain / manifest["blobs"]["manifest"]
    blob_lines = [json.loads(x) for x in blobs_path.read_text().splitlines() if x.strip()] if blobs_path.exists() else []
    if len(blob_lines) != manifest["blobs"]["count"]:
        raise VerificationError("the blob manifest and the manifest disagree on the number of blobs", "missing_artifact")
    for b in blob_lines:
        if stores is None or blob_dir is None:
            break
        try:
            store, digest = resolve(b["locator"], stores)
            if digest != b.get("stored_sha256", b["sha256"]):
                raise ArtifactError(f"locator {b['locator']} names another digest")
            target = blob_dir / b["sha256"]
            if dek is None:
                store.fetch(digest, b.get("stored_size", b.get("size")), target)
            else:
                store.fetch(digest, b.get("stored_size"), blob_dir / f"{digest}.enc")
                _decrypt_to(blob_dir / f"{digest}.enc", target, dek, f"blob:{b['sha256']}")
                (blob_dir / f"{digest}.enc").unlink()
                if chunks.sha256_file(target) != b["sha256"]:
                    raise ArtifactError(f"blob sha256:{b['sha256']} decrypts to other content")
        except (ArtifactError, envelope.EnvelopeError) as e:
            raise VerificationError(str(e), "missing_artifact") from e
        report["blobs"] += 1
        report["blob_bytes"] += b.get("size") or 0
    report["artifact_complete"] = stores is not None and report["blobs"] == len(blob_lines)
    report["manifest_sha256"] = manifest_sha
    return {"report": report, "manifest": manifest, "plain": plain}


def _decrypt_to(src: Path, dst: Path, dek: bytes, aad: str) -> None:
    try:
        dst.write_bytes(envelope.decrypt(dek, src.read_bytes(), aad))
    except envelope.EnvelopeError as e:
        raise VerificationError(str(e), "decryption_failed") from e


def _resolve_lfs(path: Path, pointer: dict, stores: dict[str, DirectoryStore]) -> None:
    """A Git LFS pointer instead of the file: the object must be recoverable independently."""
    oid = pointer.get("sha256")
    for store in stores.values():
        if oid and store.has(oid):
            store.fetch(oid, pointer.get("size"), path)
            return
    raise VerificationError(f"{path.name} is a Git LFS pointer and its object sha256:{oid} is not available",
                            "missing_lfs_object")


def migrate(manifest: dict) -> dict:
    """Apply deterministic archive-format migrations up to this importer's major version."""
    major = manifest.get("format_major")
    if manifest.get("format") != FORMAT and major == FORMAT_MAJOR:
        raise VerificationError(f"unknown format {manifest.get('format')!r}", "incompatible")
    while major is not None and major < FORMAT_MAJOR:
        step = MIGRATIONS.get(major)
        if step is None:
            raise VerificationError(f"no migration from argus-archive/{major}", "incompatible")
        manifest = step(manifest)
        major = manifest.get("format_major")
    if major != FORMAT_MAJOR:
        raise VerificationError(f"argus-archive/{major} is newer than this importer supports", "incompatible")
    return manifest
