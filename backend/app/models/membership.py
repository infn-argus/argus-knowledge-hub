from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Membership(Base):
    """A user's rights on one workspace, split into two independent resource
    groups: objects & types (schemas/assets/relations/labels/global values/
    imports) and tickets (issues/comments) — a user can e.g. read-only on
    objects but full read/write on tickets, or vice versa.

    Populated today by explicit admin/owner grant; the same table a future
    Keycloak-group-sync step would populate automatically once INFN's LDAP-backed
    Keycloak is wired up — the row shape doesn't need to change, only how rows get
    created.
    """

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # Objects & types (schemas, assets, relations, labels, global values, imports).
    can_read: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create: Mapped[bool] = mapped_column(Boolean, default=False)
    can_modify: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False)

    # Tickets (issues + issue comments) — independent from the flags above.
    can_read_tickets: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create_tickets: Mapped[bool] = mapped_column(Boolean, default=False)
    can_modify_tickets: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete_tickets: Mapped[bool] = mapped_column(Boolean, default=False)

    # Documents — independent from the flags above. can_approve_documents
    # gates the review-workflow transitions (approve/reject/publish), a
    # narrower authority than general edit rights in a real doc-control system.
    can_read_documents: Mapped[bool] = mapped_column(Boolean, default=True)
    can_create_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    can_modify_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    can_delete_documents: Mapped[bool] = mapped_column(Boolean, default=False)
    can_approve_documents: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
