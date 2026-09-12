from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin, WorkspaceScopedMixin


class Schema(Base, WorkspaceScopedMixin, TimestampMixin):
    __tablename__ = "schemas"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_concrete: Mapped[bool] = mapped_column(Boolean, default=True)
    parent_schema_uid: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("schemas.uid", ondelete="CASCADE"), nullable=True
    )
    attributes: Mapped[list] = mapped_column(JSONB, default=list)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    icon_attachment_uid: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Visible/referenceable from any workspace when true; editing/deleting still
    # requires permission in the workspace that owns it (workspace_id, unchanged).
    is_global: Mapped[bool] = mapped_column(Boolean, default=False)
    # "objects" (schemas/assets tree, default) or "tickets" (configurable
    # ticket types, shown separately). Purely organizational — permission
    # checks stay keyed off which router handles the request, not this field.
    applies_to: Mapped[str] = mapped_column(String, default="objects")
