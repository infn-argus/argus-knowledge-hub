from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    # When set, every schema owned by this workspace (any applies_to) is
    # cascaded to is_global=True too — see seed_default_global_values's
    # sibling, _cascade_global_to_workspace, in this router.
    is_global: Mapped[bool] = mapped_column(Boolean, default=False)

    # Fallback rights for any authenticated user with no explicit Membership
    # row in this workspace. All unchecked by default — a workspace stays
    # invite-only until an admin/owner opts in to some level of open access.
    default_can_read: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_create: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_modify: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_delete: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_read_tickets: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_create_tickets: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_modify_tickets: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_delete_tickets: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_read_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_create_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_modify_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_delete_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    default_can_approve_documents: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
