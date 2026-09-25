"""The `equipment_class` vocabulary of `Other Equipment` and its governance
(asset-model-revision §5.5). Owned by the catalogue."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EquipmentClass(Base):
    __tablename__ = "equipment_classes"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    # active (assignable) | promoted (now a type of its own) | deprecated
    status: Mapped[str] = mapped_column(String, default="active")
    promoted_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    added_by: Mapped[str] = mapped_column(String)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    note: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class EquipmentClassRequest(Base):
    """Someone asking for a class-specific attribute (a promotion threshold)."""
    __tablename__ = "equipment_class_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    class_name: Mapped[str] = mapped_column(String, index=True)
    attribute: Mapped[str] = mapped_column(String)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    requested_by: Mapped[str] = mapped_column(String)
    workspace_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EquipmentClassReview(Base):
    """A promotion review, opened when a class meets a threshold."""
    __tablename__ = "equipment_class_reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    class_name: Mapped[str] = mapped_column(String, index=True)
    triggers: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String, default="open")        # open | promoted | declined
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
