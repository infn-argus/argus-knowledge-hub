from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AssetTicket(Base):
    __tablename__ = "asset_tickets"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    asset_uid: Mapped[str] = mapped_column(String, ForeignKey("assets.uid", ondelete="CASCADE"), index=True)
    ticket_key: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    created: Mapped[object] = mapped_column(DateTime(timezone=True))
    updated: Mapped[object] = mapped_column(DateTime(timezone=True))
    backend_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    backend_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class AssetComment(Base):
    __tablename__ = "asset_comments"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    asset_uid: Mapped[str] = mapped_column(String, ForeignKey("assets.uid", ondelete="CASCADE"), index=True)
    author: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(String)
    created: Mapped[object] = mapped_column(DateTime(timezone=True))
    updated: Mapped[object] = mapped_column(DateTime(timezone=True))
    backend_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    backend_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class AssetHistory(Base):
    __tablename__ = "asset_history"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    asset_uid: Mapped[str] = mapped_column(String, ForeignKey("assets.uid", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String)
    author: Mapped[str] = mapped_column(String)
    details: Mapped[str] = mapped_column(String)
    timestamp: Mapped[object] = mapped_column(DateTime(timezone=True))
    backend_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class AssetLabel(Base):
    __tablename__ = "asset_labels"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    asset_uid: Mapped[str] = mapped_column(String, ForeignKey("assets.uid", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(String)
    namespace: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    issuer: Mapped[str] = mapped_column(String)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
