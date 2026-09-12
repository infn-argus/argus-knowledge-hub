"""Reversible encryption for third-party credentials we need to hold onto
(saved import configurations' PATs) so a later "Run" click can use them
without asking again — unlike our own API tokens (see app/auth.py), which
are only ever stored as a one-way hash because we never need the raw value
back.
"""
import base64
import hashlib
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = os.environ.get("IMPORT_SECRETS_KEY")
    if not key:
        raise RuntimeError(
            "IMPORT_SECRETS_KEY is not set — required to store import configuration "
            "credentials. Generate one with: python -c \"from cryptography.fernet import "
            "Fernet; print(Fernet.generate_key().decode())\" and set it as an env var."
        )
    # Accept either a raw Fernet key or an arbitrary passphrase, so ops
    # doesn't have to hand-generate a Fernet-formatted key specifically.
    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError):
        derived = base64.urlsafe_b64encode(hashlib.sha256(key.encode("utf-8")).digest())
        return Fernet(derived)


def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise RuntimeError("Could not decrypt stored credential — IMPORT_SECRETS_KEY may have changed") from e
