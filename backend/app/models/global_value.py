from typing import Optional

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin, WorkspaceScopedMixin


class GlobalValue(Base, WorkspaceScopedMixin, TimestampMixin):
    __tablename__ = "global_values"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    key: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    # "objects" | "tickets" | "documents" — the same key/name (e.g. "status")
    # is allowed to exist independently in each context.
    applies_to: Mapped[str] = mapped_column(String, default="objects")
    options: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    default_value: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    constraints: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    unique: Mapped[bool] = mapped_column(Boolean, default=False)
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    multi_value: Mapped[bool] = mapped_column(Boolean, default=False)
    min_cardinality: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_cardinality: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    egu: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    allowed_egu_list: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    read_only: Mapped[bool] = mapped_column(Boolean, default=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system_default: Mapped[bool] = mapped_column(Boolean, default=False)
