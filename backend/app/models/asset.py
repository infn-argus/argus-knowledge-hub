from typing import Optional

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin, WorkspaceScopedMixin, utcnow


class Asset(Base, WorkspaceScopedMixin, TimestampMixin):
    __tablename__ = "assets"

    uid: Mapped[str] = mapped_column(String, primary_key=True)
    schema_uid: Mapped[str] = mapped_column(
        String, ForeignKey("schemas.uid", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    avatar_icon_uid: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    inbound_relations: Mapped[list] = mapped_column(ARRAY(String), default=list)
    outbound_relations: Mapped[list] = mapped_column(ARRAY(String), default=list)
    deleted_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Visible/referenceable from any workspace when true; editing/deleting still
    # requires permission in the workspace that owns it (workspace_id, unchanged).
    is_global: Mapped[bool] = mapped_column(Boolean, default=False)


class Relation(Base, WorkspaceScopedMixin):
    __tablename__ = "relations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_asset_uid: Mapped[str] = mapped_column(
        String, ForeignKey("assets.uid", ondelete="CASCADE"), index=True
    )
    to_asset_uid: Mapped[str] = mapped_column(
        String, ForeignKey("assets.uid", ondelete="CASCADE"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
