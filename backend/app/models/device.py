"""Devices that run a field client (asset-model-revision §24.3, §24.5).

A device registers when a person signs in on it. Revoking it (by its owner
or an administrator) makes its next request answer 401 `revoked`, and the
client wipes its cache, drafts and tokens. Refresh tokens are revoked at the
identity provider too; this registry is what ARGUS itself can enforce.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    principal: Mapped[str] = mapped_column(String, index=True)       # user id, or "pat:<workspace>"
    installation_id: Mapped[str] = mapped_column(String)             # the app's per-install id
    platform: Mapped[str] = mapped_column(String)                    # android | ios | web | …
    app_version: Mapped[str] = mapped_column(String)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
