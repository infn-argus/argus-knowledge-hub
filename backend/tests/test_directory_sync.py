"""The directory sync's three rules, each guarding something that cannot be
reconstructed once lost: identities that attribute values point at, local
edits, and the link between a directory entry and a real sign-in.
"""
import secrets

import pytest
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models.group import Group, GroupMember
from app.models.user import User
from app.services.directory.base import DirectoryGroup, DirectoryPerson
from app.services.directory_sync import sync_directory


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


class FakeDirectory:
    """Stands in for LDAP so the rules can be exercised without a server."""

    name = "ldap"

    def __init__(self, people, groups):
        self._people = people
        self._groups = groups

    def people(self):
        return list(self._people)

    def groups(self):
        return list(self._groups)


def _person(suffix, uid, name="Person", active=True):
    return DirectoryPerson(
        dn=f"uid={uid}-{suffix},ou=people,dc=test",
        username=f"{uid}-{suffix}",
        email=f"{uid}-{suffix}@test.invalid",
        name=name,
        active=active,
    )


def _group(suffix, cn, members):
    return DirectoryGroup(
        dn=f"cn={cn}-{suffix},ou=groups,dc=test",
        name=f"{cn}-{suffix}",
        description="d",
        member_dns=[p.dn for p in members],
    )


def test_sync_creates_people_groups_and_memberships():
    suffix = secrets.token_hex(4)
    alice, bob = _person(suffix, "alice", "Alice"), _person(suffix, "bob", "Bob")
    team = _group(suffix, "laser", [alice, bob])

    db = SessionLocal()
    stats = sync_directory(db, FakeDirectory([alice, bob], [team]))
    assert stats["users_created"] == 2
    assert stats["groups_created"] == 1
    assert stats["memberships_added"] == 2

    group = db.scalar(select(Group).where(Group.dn == team.dn))
    assert group.source == "ldap" and group.active
    members = db.scalars(select(GroupMember).where(GroupMember.group_uid == group.uid)).all()
    assert len(members) == 2

    # A person's id is ours, not the directory's — attribute values store it.
    user = db.scalar(select(User).where(User.dn == alice.dn))
    assert user.id != alice.dn
    assert user.oidc_sub is None
    db.close()


def test_sync_is_idempotent():
    suffix = secrets.token_hex(4)
    alice = _person(suffix, "alice")
    team = _group(suffix, "laser", [alice])
    directory = FakeDirectory([alice], [team])

    db = SessionLocal()
    sync_directory(db, directory)
    second = sync_directory(db, directory)
    assert second["users_created"] == 0
    assert second["groups_created"] == 0
    assert second["memberships_added"] == 0
    assert second["memberships_removed"] == 0
    assert second["users_deactivated"] == 0
    db.close()


def test_departed_people_and_groups_are_deactivated_never_deleted():
    """A "user"-type attribute value stores a User.id and a role binding will
    store a Group.uid; deleting either row would cascade those away and erase
    who owned what."""
    suffix = secrets.token_hex(4)
    alice, bob = _person(suffix, "alice"), _person(suffix, "bob")
    team = _group(suffix, "laser", [alice, bob])

    db = SessionLocal()
    sync_directory(db, FakeDirectory([alice, bob], [team]))
    bob_id = db.scalar(select(User.id).where(User.dn == bob.dn))
    group_uid = db.scalar(select(Group.uid).where(Group.dn == team.dn))

    # Bob leaves the institute and the team is dissolved.
    stats = sync_directory(db, FakeDirectory([alice], []))
    assert stats["users_deactivated"] == 1
    assert stats["groups_deactivated"] == 1

    bob_row = db.get(User, bob_id)
    assert bob_row is not None and bob_row.active is False
    group_row = db.get(Group, group_uid)
    assert group_row is not None and group_row.active is False
    db.close()


def test_sync_leaves_local_groups_and_hand_added_members_alone():
    suffix = secrets.token_hex(4)
    alice = _person(suffix, "alice")
    team = _group(suffix, "laser", [alice])

    db = SessionLocal()
    sync_directory(db, FakeDirectory([alice], [team]))

    local_group = Group(uid=f"local-{suffix}", name=f"Local {suffix}", source="local")
    db.add(local_group)
    alice_id = db.scalar(select(User.id).where(User.dn == alice.dn))
    db.add(GroupMember(group_uid=local_group.uid, user_id=alice_id, source="local"))
    # Someone added by hand to a directory-managed group: a deliberate local
    # override the sync must not undo.
    outsider = User(id=f"out-{suffix}", email=f"out-{suffix}@test.invalid", source="local")
    db.add(outsider)
    db.flush()
    synced_group_uid = db.scalar(select(Group.uid).where(Group.dn == team.dn))
    db.add(GroupMember(group_uid=synced_group_uid, user_id=outsider.id, source="local"))
    db.commit()

    sync_directory(db, FakeDirectory([alice], [team]))

    assert db.get(Group, local_group.uid).active is True
    assert db.get(User, outsider.id).active is True
    still_there = db.scalars(
        select(GroupMember).where(GroupMember.group_uid == synced_group_uid)
    ).all()
    assert {m.user_id for m in still_there} == {alice_id, outsider.id}
    db.close()


def test_an_existing_oidc_user_is_claimed_by_email_not_duplicated():
    """Someone who signed in before the directory knew them must end up as
    one person, keeping the id their attribute values already reference."""
    suffix = secrets.token_hex(4)
    alice = _person(suffix, "alice", "Alice Directory")

    db = SessionLocal()
    existing = User(
        id=f"firebase-sub-{suffix}", oidc_sub=f"firebase-sub-{suffix}",
        email=alice.email, name="Alice", source="oidc",
    )
    db.add(existing)
    db.commit()

    stats = sync_directory(db, FakeDirectory([alice], []))
    assert stats["users_created"] == 0
    assert stats["users_updated"] == 1

    matches = db.scalars(select(User).where(User.email == alice.email)).all()
    assert len(matches) == 1
    user = matches[0]
    assert user.id == f"firebase-sub-{suffix}"   # unchanged: data points here
    assert user.oidc_sub == f"firebase-sub-{suffix}"
    assert user.dn == alice.dn                    # now linked to the directory
    assert user.source == "oidc"                  # a real sign-in, not invented
    db.close()


def test_embedded_directory_is_a_usable_organisation():
    """The fallback exists so role bindings, group attributes and pickers can
    be exercised with no LDAP; it has to contain the awkward shapes too."""
    from app.services.directory import EmbeddedDirectory

    directory = EmbeddedDirectory()
    people, groups = directory.people(), directory.groups()
    assert len(people) >= 5 and len(groups) >= 5
    assert any(not p.active for p in people), "needs a departed person"
    assert any(g.member_dns == [] for g in groups), "needs an empty group"
    # Someone in more than one group, so overlapping grants are exercisable.
    counts: dict[str, int] = {}
    for g in groups:
        for dn in g.member_dns:
            counts[dn] = counts.get(dn, 0) + 1
    assert max(counts.values()) >= 3

    db = SessionLocal()
    stats = sync_directory(db, directory)
    assert stats["provider"] == "embedded"
    assert stats["groups_created"] == len(groups)
    db.close()
