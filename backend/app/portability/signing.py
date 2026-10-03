"""Signatures on checkpoints, and the keys behind them.

One Ed25519 key signs both the checkpoint (`signature.json`, over `checksums.sha256`) and, through
Git's SSH signing, the commit and the tag that publish it. The private key lives outside ARGUS's
database and outside every repository: a file named by `ARGUS_PORTABILITY_SIGNING_KEY` (in
production, mounted from the institution's secret store; see docs/operations.md). Verifiers trust
the public keys in an OpenSSH *allowed signers* file, `ARGUS_PORTABILITY_TRUSTED_KEYS`.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ALGORITHM = "ed25519"
NAMESPACE = "argus-archive"


class SignatureError(ValueError):
    pass


@dataclass
class Signer:
    key_path: Path
    principal: str

    @property
    def private(self) -> Ed25519PrivateKey:
        key = serialization.load_ssh_private_key(self.key_path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise SignatureError("the signing key must be Ed25519")
        return key

    @property
    def public_openssh(self) -> str:
        return self.private.public_key().public_bytes(serialization.Encoding.OpenSSH,
                                                      serialization.PublicFormat.OpenSSH).decode()

    @property
    def key_id(self) -> str:
        return key_id(self.private.public_key())


def key_id(public: Ed25519PublicKey) -> str:
    raw = public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return "SHA256:" + base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip("=")


def configured_signer() -> Optional[Signer]:
    path = os.environ.get("ARGUS_PORTABILITY_SIGNING_KEY")
    if not path:
        return None
    return Signer(Path(path), os.environ.get("ARGUS_PORTABILITY_SIGNER", "argus-portability"))


def new_key(path: Path) -> Signer:
    """A fresh key (tests and first set-up; production keys come from the secret store)."""
    key = Ed25519PrivateKey.generate()
    path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH,
                                       serialization.NoEncryption()))
    os.chmod(path, 0o600)
    return Signer(path, "argus-portability")


def allowed_signers_line(signer: Signer) -> str:
    return f'{signer.principal} namespaces="git,{NAMESPACE}" {signer.public_openssh}\n'


def trusted_keys(path: Optional[Path] = None) -> dict[str, tuple[str, Ed25519PublicKey]]:
    """key id → (principal, key) from an allowed-signers file."""
    path = path or (Path(p) if (p := os.environ.get("ARGUS_PORTABILITY_TRUSTED_KEYS")) else None)
    out: dict[str, tuple[str, Ed25519PublicKey]] = {}
    if path is None or not path.exists():
        return out
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        parts = raw.split()
        principal = parts[0]
        key_at = next(i for i, p in enumerate(parts) if p.startswith("ssh-"))
        public = serialization.load_ssh_public_key(" ".join(parts[key_at:key_at + 2]).encode())
        if isinstance(public, Ed25519PublicKey):
            out[key_id(public)] = (principal, public)
    return out


def _message(checksums_sha256: str, manifest_sha256: str) -> bytes:
    return json.dumps({"namespace": NAMESPACE, "checksums_sha256": checksums_sha256,
                       "manifest_sha256": manifest_sha256}, sort_keys=True).encode()


def sign_checkpoint(signer: Signer, checksums_sha256: str, manifest_sha256: str) -> dict:
    sig = signer.private.sign(_message(checksums_sha256, manifest_sha256))
    return {"algorithm": ALGORITHM, "key_id": signer.key_id, "principal": signer.principal,
            "public_key": signer.public_openssh, "checksums_sha256": checksums_sha256,
            "manifest_sha256": manifest_sha256, "signature": base64.b64encode(sig).decode()}


def verify_checkpoint(signature: dict, checksums_sha256: str, manifest_sha256: str,
                      trusted: dict[str, tuple[str, Ed25519PublicKey]]) -> str:
    """The trusted principal that signed, or SignatureError. The public key inside the file is
    informative only: what counts is a key the verifier already trusts."""
    if signature.get("algorithm") != ALGORITHM:
        raise SignatureError(f"unsupported signature algorithm {signature.get('algorithm')!r}")
    if signature.get("checksums_sha256") != checksums_sha256 or signature.get("manifest_sha256") != manifest_sha256:
        raise SignatureError("the signature is over different checksums or a different manifest")
    entry = trusted.get(signature.get("key_id", ""))
    if entry is None:
        raise SignatureError(f"signed by {signature.get('key_id')}, which is not a trusted key")
    try:
        entry[1].verify(base64.b64decode(signature["signature"]), _message(checksums_sha256, manifest_sha256))
    except (InvalidSignature, ValueError, KeyError) as e:
        raise SignatureError("the checkpoint signature does not verify") from e
    return entry[0]
