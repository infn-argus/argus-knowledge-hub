import hashlib
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional, Union

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth_oidc import oidc_configured, verify_oidc_token
from app.db import get_db
from app.models.api_token import ApiToken
from app.models.user import User
from app.services.permissions import resolve_permission

TOKEN_PEPPER = os.environ["TOKEN_PEPPER"]

# auto_error=False: HTTPBearer's own auto_error path returns 403 on a
# missing header, which is inconsistent with the 401 an invalid/revoked
# token gets below. Handle the missing-header case ourselves so every
# auth failure is a 401.
security = HTTPBearer(auto_error=False)

Action = Literal["read", "create", "modify", "delete", "approve"]
Resource = Literal["objects", "tickets", "documents"]


def hash_token(raw_token: str) -> str:
    return hashlib.sha256((TOKEN_PEPPER + raw_token).encode("utf-8")).hexdigest()


@dataclass
class PatIdentity:
    workspace_id: str


@dataclass
class OidcIdentity:
    user: User


Identity = Union[PatIdentity, OidcIdentity]


def _resolve_oidc_user(db: Session, claims: dict) -> User:
    """Find the person behind a verified token, in the order that avoids
    creating a second row for someone who already exists:

    1. by the subject we recorded at their last sign-in;
    2. by the id, for accounts created before subjects were stored
       separately — their id *is* the subject, and every "user"-type
       attribute value in the database already points at it;
    3. by email, which is how someone the directory imported before they
       ever signed in gets claimed rather than duplicated.
    """
    sub = claims["sub"]
    email = claims.get("email", "")

    user = db.scalar(select(User).where(User.oidc_sub == sub))
    if user is None:
        user = db.get(User, sub)
    if user is None and email:
        user = db.scalar(select(User).where(User.email == email))

    if user is None:
        user = User(id=str(uuid.uuid4()), oidc_sub=sub, email=email, name=claims.get("name"))
        db.add(user)
        db.flush()
        return user

    user.oidc_sub = sub
    if email:
        user.email = email
    user.name = claims.get("name", user.name)
    # Signing in is proof the account is live, whatever a stale directory
    # sync may have concluded.
    user.active = True
    return user


def get_identity(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Identity:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    raw_token = credentials.credentials

    token_hash = hash_token(raw_token)
    token = db.scalar(
        select(ApiToken).where(
            ApiToken.token_hash == token_hash, ApiToken.revoked_at.is_(None)
        )
    )
    if token is not None:
        token.last_used_at = datetime.now(timezone.utc)
        db.commit()
        return PatIdentity(workspace_id=token.workspace_id)

    if oidc_configured():
        try:
            claims = verify_oidc_token(raw_token)
        except jwt.PyJWTError:
            pass
        else:
            user = _resolve_oidc_user(db, claims)
            user.last_login_at = datetime.now(timezone.utc)
            db.commit()
            return OidcIdentity(user=user)

    raise HTTPException(status_code=401, detail="Invalid or revoked token")


def get_current_user_id(identity: Identity = Depends(get_identity)) -> Optional[str]:
    """The acting OIDC user's id, or None for a PAT (which has no person
    behind it) — used to stamp "current_user"-type attributes on write."""
    return identity.user.id if isinstance(identity, OidcIdentity) else None


def require_permission(action: Action, resource: Resource = "objects"):
    def dependency(
        identity: Identity = Depends(get_identity),
        db: Session = Depends(get_db),
        x_workspace_id: Optional[str] = Header(default=None, alias="X-Workspace-Id"),
    ) -> str:
        if isinstance(identity, PatIdentity):
            return identity.workspace_id

        if not x_workspace_id:
            raise HTTPException(status_code=400, detail="Missing X-Workspace-Id header")
        if not resolve_permission(db, identity.user, x_workspace_id, action, resource):
            raise HTTPException(status_code=403, detail="Not permitted")
        return x_workspace_id

    return dependency
