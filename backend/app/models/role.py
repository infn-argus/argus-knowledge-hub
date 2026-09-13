from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class Role(Base, TimestampMixin):
    """A named set of permissions.

    Roles are data rather than code so a deployment can add one without a
    release — INFN will want shapes we haven't thought of. The system roles
    are seeded and flagged, so the UI can stop anyone editing the meaning of
    "owner" out from under the people who hold it.

    `permissions` maps a resource to the actions allowed on it:

        {"objects": ["read", "create"],
         "tickets": ["read"],
         "documents": ["read"],
         "workspace": ["manage_members"]}

    The resources and actions are exactly the ones require_permission()
    already takes, so the enforcement points don't change.
    """

    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    # Where a role is shown in a picker; also the tie-breaker when reporting
    # "the highest role someone holds".
    rank: Mapped[int] = mapped_column(default=0)


class RoleBinding(Base):
    """Grants a role to a user or a group, on one workspace.

    Binding a group is the point of the whole exercise: a division of eighty
    people gets access in one row instead of eighty. A subject may hold
    several bindings; the permissions union.
    """

    __tablename__ = "role_bindings"
    __table_args__ = (UniqueConstraint("workspace_id", "subject_type", "subject_id", "role_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    # "user" | "group". Not a foreign key to either table, because the two
    # targets live in different tables; the routers validate existence.
    subject_type: Mapped[str] = mapped_column(String)
    subject_id: Mapped[str] = mapped_column(String, index=True)
    role_id: Mapped[str] = mapped_column(String, ForeignKey("roles.id", ondelete="CASCADE"))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
