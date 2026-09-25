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
    restricted_grants: tuple = ()


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
        return PatIdentity(workspace_id=token.workspace_id,
                           restricted_grants=tuple(token.restricted_grants or ()))

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


def grants_of(db: Session, identity: Identity, workspace_id: str):
    """The restricted classes this viewer may see in this workspace (§4.3):
    a token's own grants, a person's `restricted` role permissions, or
    everything for an administrator."""
    from app.services.permissions import effective_permissions
    from app.services.visibility import Grants
    if isinstance(identity, PatIdentity):
        return Grants(identity.restricted_grants)
    if identity.user.is_admin:
        return Grants.all()
    return Grants(effective_permissions(db, identity.user, workspace_id).get("restricted", set()))


def get_grants(
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
    x_workspace_id: Optional[str] = Header(default=None, alias="X-Workspace-Id"),
):
    workspace_id = identity.workspace_id if isinstance(identity, PatIdentity) else x_workspace_id
    return grants_of(db, identity, workspace_id or "")


def _lenient_grants(authorization: Optional[str], workspace_id: Optional[str]):
    """Grants for whoever the bearer token names, or none. Never raises:
    authentication itself is each endpoint's own dependency."""
    from app.db import SessionLocal
    from app.services.visibility import NONE, Grants
    if not authorization or not authorization.lower().startswith("bearer "):
        return NONE
    raw = authorization.split(" ", 1)[1].strip()
    db = SessionLocal()
    try:
        token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_token(raw),
                                                 ApiToken.revoked_at.is_(None)))
        if token is not None:
            return Grants(token.restricted_grants or ())
        if oidc_configured():
            try:
                claims = verify_oidc_token(raw)
            except jwt.PyJWTError:
                return NONE
            user = db.scalar(select(User).where(User.oidc_sub == claims["sub"])) or db.get(User, claims["sub"])
            if user is not None and workspace_id:
                return grants_of(db, OidcIdentity(user=user), workspace_id)
            if user is not None and user.is_admin:
                return Grants.all()
        return NONE
    finally:
        db.close()


async def bind_grants(
    authorization: Optional[str] = Header(default=None),
    x_workspace_id: Optional[str] = Header(default=None, alias="X-Workspace-Id"),
) -> None:
    """App-wide: record the viewer's restricted-class grants for this request
    (I-ACL-1). Async on purpose — a value set here is inherited by the
    endpoint, which runs in a copy of this context."""
    from starlette.concurrency import run_in_threadpool
    from app.services.visibility import set_current_grants
    set_current_grants(await run_in_threadpool(_lenient_grants, authorization, x_workspace_id))
