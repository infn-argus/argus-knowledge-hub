"""Portability set-up registered from the web app (app/portability/ui_config.py): repositories with their
credentials, the keys an import trusts, and this installation's signing key. The deployment's own settings
(ARGUS_PORTABILITY_*) come first and are never stored here. Private keys and tokens are encrypted
(services/crypto.py) and never returned by the API.

A row is `pending` until it may be used: under a policy with separation of duties another administrator
approves it; an SSH repository also needs its server's host keys confirmed."""
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import utcnow


class PortabilityRepository(Base):
    __tablename__ = "portability_repositories"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String, default="other")          # github | gitlab | other | local
    auth: Mapped[str] = mapped_column(String)                              # ssh | https | none | local
    encrypted_private_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    public_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # [{line, type, fingerprint}] from ssh-keyscan; pinned once a person confirms the fingerprints.
    host_keys: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    host_keys_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="pending")          # pending | active
    created_by: Mapped[str] = mapped_column(String)
    created_at = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    approved_at = mapped_column(DateTime(timezone=True), nullable=True)
    last_test: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class PortabilityTrustedKey(Base):
    __tablename__ = "portability_trusted_keys"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    principal: Mapped[str] = mapped_column(String)
    line: Mapped[str] = mapped_column(Text)                                # an allowed-signers line
    key_id: Mapped[str] = mapped_column(String)
    note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_by: Mapped[str] = mapped_column(String)
    created_at = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    approved_at = mapped_column(DateTime(timezone=True), nullable=True)


class PortabilitySigningKey(Base):
    __tablename__ = "portability_signing_keys"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    principal: Mapped[str] = mapped_column(String)
    encrypted_private_key: Mapped[str] = mapped_column(Text)
    public_line: Mapped[str] = mapped_column(Text)                         # its allowed-signers line
    key_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")         # pending | active | retired
    created_by: Mapped[str] = mapped_column(String)
    created_at = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    approved_at = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at = mapped_column(DateTime(timezone=True), nullable=True)


class PortabilityStore(Base):
    """An artifact store registered in the web app: a directory inside the portability area
    (<ARGUS_PORTABILITY_ROOT>/stores/<name>), so it is on the installation's portability volume."""
    __tablename__ = "portability_stores"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_by: Mapped[str] = mapped_column(String)
    created_at = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    approved_at = mapped_column(DateTime(timezone=True), nullable=True)
