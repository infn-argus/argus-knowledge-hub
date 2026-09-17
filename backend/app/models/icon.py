from typing import Optional

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin, WorkspaceScopedMixin


class Icon(Base, WorkspaceScopedMixin, TimestampMixin):
    """A reusable picture, chosen from a shared library rather than owned
    exclusively by one type — unlike an object's avatar or an attachment,
    the same icon can be referenced by any number of schemas at once, so
    nothing here deletes it just because one type stopped using it."""

    __tablename__ = "icons"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    mime_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    storage_path: Mapped[str] = mapped_column(String)
    # Visible/referenceable from any workspace when true; editing/deleting still
    # requires permission in the workspace that owns it (workspace_id, unchanged) —
    # the same contract schemas, assets and documents already have.
    is_global: Mapped[bool] = mapped_column(Boolean, default=False)
