"""Envelope encryption of restricted archives (docs/export-import-design.md §7.1).

* A new 256-bit data-encryption key (DEK) per export. Every data chunk and every blob of an
  encrypted export is AES-256-GCM encrypted with it, with a random 96-bit nonce per file and the
  file's name (or digest) as associated data.
* The DEK is wrapped once per recipient: X25519 with an ephemeral key, HKDF-SHA256 to a key-wrapping
  key, AES-256-GCM over the DEK. Recipients are the public keys configured for the destination;
  ARGUS never holds a recipient's private key, and the archive never holds the DEK in clear.
* The manifest records the algorithms, every recipient's key id, ephemeral public key and wrapped
  DEK, and the SHA-256 of each encrypted file. The checksums are over the encrypted bytes, and the
  signature covers the checksums and the manifest — encryption metadata included.
* Decrypting needs a recipient private key, supplied only for an import session (a mounted secret,
  `ARGUS_PORTABILITY_DECRYPTION_KEYS`), never stored in ARGUS, Git or the archive.

Revoking a download token, or an export, does not revoke anything cryptographically: whoever holds
a copy and a recipient key can still decrypt it. Removing a recipient affects later exports only.
"""
from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"ARGUS-ENC-1\n"
ALGORITHM = "AES-256-GCM"
WRAPPING = "X25519-HKDF-SHA256-AES-256-GCM"
INFO = b"argus-archive/1 data-key wrap"


class EnvelopeError(ValueError):
    pass


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _raw(pub: X25519PublicKey) -> bytes:
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def key_id(pub: X25519PublicKey) -> str:
    return "x25519:" + hashlib.sha256(_raw(pub)).hexdigest()[:16]


@dataclass
class Recipient:
    name: str
    public: X25519PublicKey

    @property
    def key_id(self) -> str:
        return key_id(self.public)


def load_recipients(path: Path) -> list[Recipient]:
    """`<name> <base64 raw X25519 public key>` per line."""
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, b64 = line.split()[:2]
        out.append(Recipient(name, X25519PublicKey.from_public_bytes(base64.b64decode(b64))))
    if not out:
        raise EnvelopeError(f"{path} names no recipient")
    return out


def new_recipient_key(private_path: Path, name: str) -> str:
    """A recipient key pair: the private key written (0600) for its holder, the public line returned
    for the destination's recipients file. For set-up and tests; real keys belong to their holders."""
    key = X25519PrivateKey.generate()
    private_path.write_text(_b64(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                                                   serialization.NoEncryption())) + "\n")
    os.chmod(private_path, 0o600)
    return f"{name} {_b64(_raw(key.public_key()))}\n"


def _kek(shared: bytes, eph: bytes, recipient: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=eph + recipient, info=INFO).derive(shared)


@dataclass
class Envelope:
    dek: bytes
    recipients: list

    @classmethod
    def new(cls, recipients: list[Recipient]) -> "Envelope":
        if not recipients:
            raise EnvelopeError("an encrypted export needs at least one recipient")
        return cls(AESGCM.generate_key(bit_length=256), recipients)

    def metadata(self) -> dict:
        wrapped = []
        for r in self.recipients:
            eph = X25519PrivateKey.generate()
            eph_pub = _raw(eph.public_key())
            kek = _kek(eph.exchange(r.public), eph_pub, _raw(r.public))
            nonce = os.urandom(12)
            wrapped.append({"recipient": r.name, "key_id": r.key_id, "ephemeral_public": _b64(eph_pub),
                            "nonce": _b64(nonce),
                            "wrapped_key": _b64(AESGCM(kek).encrypt(nonce, self.dek, r.key_id.encode()))})
        return {"algorithm": ALGORITHM, "key_wrapping": WRAPPING, "recipients": wrapped}

    def encrypt(self, data: bytes, aad: str) -> bytes:
        nonce = os.urandom(12)
        return MAGIC + nonce + AESGCM(self.dek).encrypt(nonce, data, aad.encode())


def is_encrypted(data: bytes) -> bool:
    return data.startswith(MAGIC)


def unwrap(meta: dict, private_keys: list[X25519PrivateKey]) -> bytes:
    """The DEK, from the first recipient entry one of `private_keys` opens."""
    for key in private_keys:
        kid = key_id(key.public_key())
        for w in meta.get("recipients", []):
            if w["key_id"] != kid:
                continue
            eph = base64.b64decode(w["ephemeral_public"])
            kek = _kek(key.exchange(X25519PublicKey.from_public_bytes(eph)), eph, _raw(key.public_key()))
            try:
                return AESGCM(kek).decrypt(base64.b64decode(w["nonce"]), base64.b64decode(w["wrapped_key"]),
                                           kid.encode())
            except Exception as e:  # noqa: BLE001
                raise EnvelopeError("the wrapped data key does not open with this recipient key") from e
    raise EnvelopeError("none of the available decryption keys is a recipient of this archive")


def decrypt(dek: bytes, data: bytes, aad: str) -> bytes:
    if not is_encrypted(data):
        raise EnvelopeError("not an encrypted file")
    body = data[len(MAGIC):]
    try:
        return AESGCM(dek).decrypt(body[:12], body[12:], aad.encode())
    except Exception as e:  # noqa: BLE001
        raise EnvelopeError(f"{aad}: authentication failed (tampered, or another key)") from e


def load_private_keys(directory: Optional[Path]) -> list[X25519PrivateKey]:
    """Recipient private keys for an import session: files of one base64 raw key each."""
    if directory is None or not directory.exists():
        return []
    out = []
    for p in sorted(directory.iterdir()):
        if p.is_file():
            try:
                out.append(X25519PrivateKey.from_private_bytes(base64.b64decode(p.read_text().strip())))
            except Exception:  # noqa: BLE001 — not a key file
                continue
    return out
