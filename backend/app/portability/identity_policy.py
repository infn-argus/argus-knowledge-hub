"""How people travel in an archive: the identity-export profile (docs/export-import-design.md §5.1).

Historical attribution must survive; personal data travels only as far as the profile allows.
Three things are kept apart:

  historical actor   who did something: a stable actor uid, its type, and the references from
                     claims, decisions and records — always kept, so the archive can still show that
                     several actions came from the same actor
  contact            e-mail, display name, username — current contact data, not history
  directory          DN, OIDC subject, source — integration data of one deployment

Profiles:

  full_identity               everything the users table holds (minus credentials, which have no
                              column). High-risk: needs an explicit decision and a second approver
  institutional_reference     DEFAULT. The ARGUS user uid and the OIDC subject (its issuer is the
                              instance's, in the manifest); no e-mail, DN, name or username. Actor
                              strings that are e-mails become the user uid when the person is known,
                              a pseudonym otherwise
  pseudonymized               a salted institutional hash per person (ARGUS_PORTABILITY_PSEUDONYM_SALT):
                              the same person gets the same pseudonym in every export of the
                              institution; nothing else about them
  anonymous_historical_actor  a pseudonym from a random per-export salt that is never kept: actions
                              stay grouped by actor inside the archive, nothing links them to a person

Except for `full_identity`, the transform is applied to every string of every exported row, the
same way everywhere, so the archive stays consistent with itself:

* a value equal to a known user uid, e-mail or username becomes that person's reference;
* any e-mail address inside a string (an actor field, a person stream id `person:<e-mail>@<ws>`,
  free text) becomes the reference of the person who has it, or a pseudonym.

Applied before secret scanning and hashing; the manifest records the profile and, for a salted one,
the salt's key id (never the salt).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass, field
from typing import Optional

PROFILES = ("full_identity", "institutional_reference", "pseudonymized", "anonymous_historical_actor")
DEFAULT = "institutional_reference"
HIGH_RISK = ("full_identity",)
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
PSEUDO_DOMAIN = "pseudonym.invalid"

# The identities family, per profile: which columns travel.
IDENTITY_COLUMNS = {
    "full_identity": ("id", "oidc_sub", "dn", "email", "name", "username", "source", "active", "created_at"),
    "institutional_reference": ("id", "oidc_sub", "source", "active"),
    "pseudonymized": ("id", "source", "active"),
    "anonymous_historical_actor": ("id", "active"),
}


class IdentityPolicyError(ValueError):
    pass


@dataclass
class IdentityPolicy:
    profile: str
    users: list = field(default_factory=list)        # (id, email, username) of every person in scope
    salt: Optional[bytes] = None
    _by_value: dict = field(default_factory=dict)
    _by_email: dict = field(default_factory=dict)

    @classmethod
    def make(cls, profile: Optional[str], users: list[tuple]) -> "IdentityPolicy":
        profile = profile or DEFAULT
        if profile not in PROFILES:
            raise IdentityPolicyError(f"unknown identity profile {profile!r}; one of {', '.join(PROFILES)}")
        salt = None
        if profile == "pseudonymized":
            configured = os.environ.get("ARGUS_PORTABILITY_PSEUDONYM_SALT")
            if not configured:
                raise IdentityPolicyError("the pseudonymized profile needs ARGUS_PORTABILITY_PSEUDONYM_SALT "
                                          "(an institutional secret)")
            salt = configured.encode()
        elif profile == "anonymous_historical_actor":
            salt = secrets.token_bytes(32)           # used for this export only, never stored
        p = cls(profile, list(users), salt)
        for uid, email, username in users:
            ref = p.reference(uid)
            for v in (uid, email, username):
                if v:
                    p._by_value[v] = ref
            if email:
                p._by_email[email.lower()] = ref
        return p

    @property
    def transforms(self) -> bool:
        return self.profile != "full_identity"

    def reference(self, uid: str) -> str:
        """The stable actor reference this profile gives a known person."""
        if self.profile in ("full_identity", "institutional_reference"):
            return uid
        return "actor-" + hmac.new(self.salt, f"user:{uid}".encode(), hashlib.sha256).hexdigest()[:20]

    def _unknown_email(self, email: str) -> str:
        key = self.salt or b"argus-portability/unknown-actor"
        return "actor-" + hmac.new(key, f"email:{email.lower()}".encode(), hashlib.sha256).hexdigest()[:20] + \
            f"@{PSEUDO_DOMAIN}"

    def _email(self, m: re.Match) -> str:
        email = m.group(0)
        if email.lower().endswith("@" + PSEUDO_DOMAIN):
            return email
        known = self._by_email.get(email.lower())
        return known if known else self._unknown_email(email)

    def value(self, v):
        if not self.transforms:
            return v
        if isinstance(v, str):
            if v in self._by_value:
                return self._by_value[v]
            return EMAIL.sub(self._email, v) if "@" in v else v
        if isinstance(v, list):
            return [self.value(x) for x in v]
        if isinstance(v, dict):
            return {self.value(k) if isinstance(k, str) else k: self.value(x) for k, x in v.items()}
        return v

    def row(self, family: str, row: dict) -> dict:
        if family == "identities":
            keep = IDENTITY_COLUMNS[self.profile]
            out = {k: (row.get(k) if k in row else None) for k in keep}
            out["id"] = self.reference(row["id"])
            if self.profile == "pseudonymized" and row.get("oidc_sub"):
                out["issuer_hash"] = hmac.new(self.salt, f"sub:{row['oidc_sub']}".encode(),
                                              hashlib.sha256).hexdigest()
            out["actor_type"] = "person"
            return out
        return self.value(row) if self.transforms else row

    def describe(self) -> dict:
        out = {"profile": self.profile, "identity_columns": list(IDENTITY_COLUMNS[self.profile]),
               "actors_transformed": self.transforms}
        if self.profile == "pseudonymized":
            out["salt_key_id"] = hashlib.sha256(b"salt-id:" + self.salt).hexdigest()[:16]
        if self.profile == "anonymous_historical_actor":
            out["salt"] = "per-export, not retained"
        if self.profile == "institutional_reference":
            out["issuer"] = os.environ.get("OIDC_ISSUER")
        return out
