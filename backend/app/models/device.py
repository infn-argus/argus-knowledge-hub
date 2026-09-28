"""Devices that run a field client (asset-model-revision §24.3, §24.5).

A device registers when a person signs in on it. Revoking it (by its owner
or an administrator) makes its next request answer 401 `revoked`, and the
client wipes its cache, drafts and tokens. Refresh tokens are revoked at the
identity provider too; this registry is what ARGUS itself can enforce.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
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


class IdempotencyRecord(Base):
    """What a mutating request with an `Idempotency-Key` answered (flutter-app-design §3.2).

    A retry after a lost response replays the stored answer and writes nothing (I-MOB-2). The
    same key with a different request is refused. Rows expire after the offline retention (U22)
    plus seven days.
    """
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("workspace_id", "principal", "key", name="uq_idempotency_key"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String, default="")
    principal: Mapped[str] = mapped_column(String)
    key: Mapped[str] = mapped_column(String)
    request_hash: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, default="in_progress")   # in_progress | done
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    response_headers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Upload(Base):
    """A file sent in pieces, so a phone on a weak network can resume (flutter-app-design §5.5).

    The client states the size and SHA-256 first. The server refuses anything over the limit before
    a byte is sent. It accepts pieces only at the current offset, recomputes the hash at the end,
    and removes location metadata from images. Only then can the file be attached to a record.
    """
    __tablename__ = "uploads"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    principal: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    content_type: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String)
    received: Mapped[int] = mapped_column(BigInteger, default=0)
    state: Mapped[str] = mapped_column(String, default="open")   # open | complete | attached
    storage_path: Mapped[str] = mapped_column(String)
    attachment_uid: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gps_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
