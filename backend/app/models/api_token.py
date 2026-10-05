"""API tokens: personal access tokens and robot tokens.

A **personal** token (kind "personal") acts as the person who made it: what it may do is what that person's
roles allow, narrowed by the token's scopes, and optionally fixed to one workspace. It never carries
administrator rights unless its owner is an administrator and gave it the `admin` scope.

A **robot** token (kind "robot") belongs to a workspace, not to a person: a facility's logbook uploader, a
script, the Accelerator Model Toolbox. A workspace owner (or an administrator) makes it with the scopes, the
kinds of record and the lifetime the job needs. Tokens made before kinds existed are robot tokens with every
scope, which is what they always could do.

Only the SHA-256 of the token (with the deployment's pepper) is kept; the token itself is shown once.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# What a token may be allowed to do. `admin` covers workspace administration (members, roles, robot tokens) for a
# robot, and administrator rights for a personal token whose owner is an administrator.
SCOPES = ("read", "create", "modify", "delete", "approve", "admin")
RESOURCES = ("objects", "tickets", "documents")


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String, default="robot")             # personal | robot
    # A robot's workspace; for a personal token, the one workspace it is fixed to, or None for all its owner's.
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # The person a personal token acts as.
    user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    token_hash: Mapped[str] = mapped_column(String, unique=True, index=True)
    # The first characters, to recognise a token in a list without storing it ("argus_bot_3fA9…").
    prefix: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scopes: Mapped[list] = mapped_column(JSONB, default=lambda: list(SCOPES))
    # The kinds of record it may touch; empty means all.
    resources: Mapped[list] = mapped_column(JSONB, default=list)
    # Restricted classes this token may see (§4.3), e.g. ["costs"]. A token
    # sees no restricted record unless it is granted its class.
    restricted_grants: Mapped[list] = mapped_column(JSONB, default=list)
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
