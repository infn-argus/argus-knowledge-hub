"""Generic OIDC ID-token verification, independent of the identity provider.

Configured entirely via env vars (issuer, JWKS URL, audience) so switching from
Firebase to INFN's future Keycloak is a config change, not a rewrite: only these
three values differ between providers, everything downstream (the User/Membership
model, permission checks) reads the same decoded claims regardless of issuer.

Firebase example values:
  OIDC_ISSUER   = https://securetoken.google.com/<firebase-project-id>
  OIDC_JWKS_URI = https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com
  OIDC_AUDIENCE = <firebase-project-id>
"""
import os
from functools import lru_cache

import jwt
from jwt import PyJWKClient

OIDC_ISSUER = os.environ.get("OIDC_ISSUER")
OIDC_JWKS_URI = os.environ.get("OIDC_JWKS_URI")
OIDC_AUDIENCE = os.environ.get("OIDC_AUDIENCE")


@lru_cache(maxsize=1)
def _jwk_client() -> PyJWKClient:
    # A short timeout matters here: this runs inline while a request's DB
    # session is checked out (FastAPI dependency), so a slow/unreachable JWKS
    # endpoint would otherwise hold that connection for PyJWKClient's default
    # 30s timeout instead of failing fast.
    return PyJWKClient(OIDC_JWKS_URI, timeout=5)


def oidc_configured() -> bool:
    return bool(OIDC_ISSUER and OIDC_JWKS_URI and OIDC_AUDIENCE)


def verify_oidc_token(raw_token: str) -> dict:
    """Returns the decoded claims, or raises jwt.PyJWTError if invalid."""
    signing_key = _jwk_client().get_signing_key_from_jwt(raw_token)
    return jwt.decode(
        raw_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=OIDC_AUDIENCE,
        issuer=OIDC_ISSUER,
    )
