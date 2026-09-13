"""Role resolution.

The rule that matters: grants union, never intersect, and a legacy
Membership keeps resolving — access granted before roles existed must not
disappear the moment this ships.
"""
import secrets
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models.group import Group, GroupMember
from app.models.membership import Membership
from app.models.role import Role, RoleBinding
from app.models.user import User
from app.models.workspace import Workspace
from app.services.permissions import effective_permissions, has_permission
from app.services.roles import (
    ensure_system_roles,
    matching_system_role_id,
    membership_permissions,
)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    ensure_system_roles(db)
    db.commit()
    db.close()
    yield


def _bind(db, workspace_id, subject_type, subject_id, role_id):
    db.add(RoleBinding(
        workspace_id=workspace_id, subject_type=subject_type, subject_id=subject_id,
        role_id=role_id, created_at=datetime.now(timezone.utc),
    ))


def _setup(db, suffix):
    ws = f"ws-{suffix}"
    db.add(Workspace(id=ws, name="WS"))
    user = User(id=f"u-{suffix}", email=f"u-{suffix}@test.invalid")
    db.add(user)
    db.flush()
    return ws, user


def test_a_direct_role_binding_grants_its_permissions():
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    ws, user = _setup(db, suffix)
    _bind(db, ws, "user", user.id, "agent")
    db.commit()

    granted = effective_permissions(db, user, ws)
    assert granted["tickets"] == {"read", "create", "modify"}
    assert granted["objects"] == {"read"}
    assert "delete" not in granted["tickets"]
    assert granted["workspace"] == set()
    db.close()


def test_a_group_binding_reaches_every_member():
    """The point of the exercise: a division of eighty gets access in one
    row, and someone joining the group inherits it without another grant."""
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    ws, user = _setup(db, suffix)
    group = Group(uid=f"g-{suffix}", name="Servizio Laser", source="ldap")
    db.add(group)
    db.flush()
    _bind(db, ws, "group", group.uid, "curator")
    db.commit()

    # Not a member yet: nothing.
    assert effective_permissions(db, user, ws)["objects"] == set()

    db.add(GroupMember(group_uid=group.uid, user_id=user.id, source="ldap"))
    db.commit()
    assert effective_permissions(db, user, ws)["objects"] == {"read", "create", "modify", "delete"}
    db.close()


def test_grants_union_rather_than_replace():
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    ws, user = _setup(db, suffix)
    group = Group(uid=f"g-{suffix}", name="Documentation Board", source="ldap")
    db.add(group)
    db.flush()
    db.add(GroupMember(group_uid=group.uid, user_id=user.id, source="ldap"))
    _bind(db, ws, "user", user.id, "agent")      # tickets: read/create/modify
    _bind(db, ws, "group", group.uid, "approver")  # documents: read/approve
    db.commit()

    granted = effective_permissions(db, user, ws)
    assert granted["tickets"] == {"read", "create", "modify"}
    assert granted["documents"] == {"read", "approve"}
    db.close()


def test_bindings_are_scoped_to_their_workspace():
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    ws, user = _setup(db, suffix)
    other = f"other-{suffix}"
    db.add(Workspace(id=other, name="Other"))
    _bind(db, ws, "user", user.id, "curator")
    db.commit()

    assert effective_permissions(db, user, ws)["objects"]
    assert effective_permissions(db, user, other)["objects"] == set()
    db.close()


def test_a_legacy_membership_still_resolves():
    """Access granted before roles existed must survive the deploy."""
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    ws, user = _setup(db, suffix)
    db.add(Membership(
        workspace_id=ws, user_id=user.id,
        can_read=True, can_create=True, can_modify=True, can_delete=False,
        can_read_tickets=True, can_approve_documents=True,
    ))
    db.commit()

    granted = effective_permissions(db, user, ws)
    assert granted["objects"] == {"read", "create", "modify"}
    assert granted["tickets"] == {"read"}
    assert "approve" in granted["documents"]
    assert has_permission(db, user, ws, "modify", "objects")
    assert not has_permission(db, user, ws, "delete", "objects")
    db.close()


def test_full_legacy_membership_keeps_the_right_to_grant_access():
    """The old model had no owner role: full rights on objects was exactly
    what member management checked for. Whoever set everyone else up must
    not lose the ability to do it again."""
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    ws, user = _setup(db, suffix)
    db.add(Membership(
        workspace_id=ws, user_id=user.id,
        can_read=True, can_create=True, can_modify=True, can_delete=True,
    ))
    db.commit()
    assert has_permission(db, user, ws, "manage_members", "workspace")
    db.close()


def test_admin_passes_everything_without_a_binding():
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    ws, user = _setup(db, suffix)
    user.is_admin = True
    db.commit()
    assert has_permission(db, user, ws, "delete", "documents")
    assert has_permission(db, user, ws, "manage_members", "workspace")
    db.close()


def test_only_owner_may_grant_access():
    suffix = secrets.token_hex(4)
    db = SessionLocal()
    ws, user = _setup(db, suffix)
    _bind(db, ws, "user", user.id, "curator")
    db.commit()
    # A curator has total control of the content but cannot hand out access.
    assert has_permission(db, user, ws, "delete", "objects")
    assert not has_permission(db, user, ws, "manage_members", "workspace")

    _bind(db, ws, "user", user.id, "owner")
    db.commit()
    assert has_permission(db, user, ws, "manage_members", "workspace")
    db.close()


def test_every_seeded_role_is_expressible_and_owner_matches_full_rights():
    """The migration converts a membership only when its flags mean exactly
    one role; a full-rights membership — which is what both production rows
    are — has to land on owner rather than be left behind."""
    db = SessionLocal()
    seeded = {r.id for r in db.scalars(select(Role).where(Role.is_system.is_(True)))}
    assert {"viewer", "reporter", "agent", "approver", "contributor", "curator", "owner"} <= seeded
    db.close()

    class _Full:
        pass

    full = _Full()
    for suffix in ("", "_tickets", "_documents"):
        for action in ("read", "create", "modify", "delete"):
            setattr(full, f"can_{action}{suffix}", True)
    full.can_approve_documents = True
    assert matching_system_role_id(membership_permissions(full)) == "owner"

    class _ReadOnly:
        pass

    read_only = _ReadOnly()
    for suffix in ("", "_tickets", "_documents"):
        for action in ("read", "create", "modify", "delete"):
            setattr(read_only, f"can_{action}{suffix}", action == "read")
    read_only.can_approve_documents = False
    assert matching_system_role_id(membership_permissions(read_only)) == "viewer"


def test_an_unrepresentable_membership_is_not_converted():
    """Rounding permissions up would silently widen someone's access and
    rounding them down would break their work, so such a row is left to
    resolve through the legacy path instead."""
    class _Odd:
        pass

    odd = _Odd()
    for suffix in ("", "_tickets", "_documents"):
        for action in ("read", "create", "modify", "delete"):
            setattr(odd, f"can_{action}{suffix}", False)
    # Can delete objects but cannot even read tickets: no role means this.
    odd.can_read = True
    odd.can_delete = True
    odd.can_approve_documents = False
    assert matching_system_role_id(membership_permissions(odd)) is None
