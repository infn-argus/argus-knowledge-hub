from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import utcnow


class ImportSnapshot(Base):
    """What an importer last wrote on an object, per source.

    An importer re-reading its source compares the object with this, not with
    what it is about to write: a value that differs from the snapshot was
    changed by somebody since the last import, and is kept. It is the first
    step towards the fact ledger of docs/asset-model-revision.md (§7), and the
    P0 fix for re-imports that erased manual edits (C9)."""

    __tablename__ = "import_snapshots"

    asset_uid: Mapped[str] = mapped_column(
        String, ForeignKey("assets.uid", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String, primary_key=True)
    values: Mapped[dict] = mapped_column(JSONB, default=dict)
    source_ref: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
