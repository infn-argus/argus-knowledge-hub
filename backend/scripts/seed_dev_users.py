"""Dev script: pre-create the users the local Keycloak realm signs in, and
grant each the access it's meant to demonstrate.

Six people, matched to a spread of the permission model rather than to any
real INFN person — see docs/oidc-dev-setup.md for what each is for:

    admin.test         is_admin: sees and does everything, no bindings needed
    owner.test          Owner on sparc only
    contributor.test     Contributor on sparc AND euaps — one person, two workspaces
    viewer.test          Viewer on eli only — read-only
    curator.test          Curator on btf, Viewer on accelerator-infn — different
                          roles in different workspaces, the same person
    outsider.test         no bindings anywhere — the empty-state case

A User row is normally created on first OIDC sign-in (auth.py
_resolve_oidc_user), with an id nobody can predict ahead of time. This
creates the row early instead, keyed by email; when that email actually
signs in through Keycloak, _resolve_oidc_user's own email-matching fallback
finds this same row and fills in its real oidc_sub, so identity and grants
land on one person rather than two.

Safe to run again: existing users and bindings are left alone, and running
it after seed_asset_types.py or against a hub with the six workspaces
already there is expected — this only reads workspace ids, never creates
one.
"""
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, ".")

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.role import RoleBinding  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402
from app.services.roles import ensure_system_roles  # noqa: E402

# (email, name, is_admin, [(workspace_id, role_id), ...])
TEST_USERS = [
    ("admin.test@argus.test", "Test Admin", True, []),
    ("owner.test@argus.test", "Test Owner", False, [("sparc", "owner")]),
    ("contributor.test@argus.test", "Test Contributor", False,
     [("sparc", "contributor"), ("euaps", "contributor")]),
    ("viewer.test@argus.test", "Test Viewer", False, [("eli", "viewer")]),
    ("curator.test@argus.test", "Test Curator", False,
     [("btf", "curator"), ("accelerator-infn", "viewer")]),
    ("outsider.test@argus.test", "Test Outsider", False, []),
]


def main() -> None:
    db = SessionLocal()
    try:
        ensure_system_roles(db)

        missing_ws = sorted({ws for _, _, _, bindings in TEST_USERS for ws, _ in bindings}
                            - {w.id for w in db.scalars(select(Workspace))})
        if missing_ws:
            print(f"Workspace(s) {', '.join(missing_ws)} don't exist yet — "
                  f"create them (create_token.py or import_epik8s.py) before the bindings "
                  f"that reference them will take. Continuing with the rest.")

        for email, name, is_admin, bindings in TEST_USERS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(id=str(uuid.uuid4()), email=email, name=name, is_admin=is_admin,
                           source="oidc", active=True)
                db.add(user)
                db.flush()
                print(f"created {email} ({user.id})")
            else:
                user.is_admin = is_admin
                print(f"exists  {email} ({user.id})")

            for workspace_id, role_id in bindings:
                if workspace_id in missing_ws:
                    continue
                exists = db.scalar(select(RoleBinding).where(
                    RoleBinding.workspace_id == workspace_id, RoleBinding.subject_type == "user",
                    RoleBinding.subject_id == user.id, RoleBinding.role_id == role_id))
                if exists is None:
                    db.add(RoleBinding(workspace_id=workspace_id, subject_type="user",
                                       subject_id=user.id, role_id=role_id,
                                       created_at=datetime.now(timezone.utc),
                                       created_by="seed_dev_users.py"))
                    print(f"  + {role_id} on {workspace_id}")
        db.commit()
    finally:
        db.close()

    print("\nEvery test user's Keycloak password is argus-dev (see keycloak/realm-argus-dev.json).")


if __name__ == "__main__":
    main()
