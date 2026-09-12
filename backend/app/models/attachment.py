from typing import Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin, WorkspaceScopedMixin


class Attachment(Base, WorkspaceScopedMixin, TimestampMixin):
    __tablename__ = "attachments"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    # Nullable: schema-icon attachments (see schemas.py's icon upload endpoint) have
    # no owning asset.
    asset_uid: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("assets.uid", ondelete="CASCADE"), nullable=True, index=True
    )
    document_revision_uid: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("document_revisions.uid", ondelete="CASCADE"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String)
    mime_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    storage_path: Mapped[str] = mapped_column(String)
    backend_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    backend_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
