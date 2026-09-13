"""Mirror a directory into users, groups and group memberships.

Three rules hold this together, and each one exists because breaking it
loses data that cannot be reconstructed:

1. Nothing is ever hard-deleted. A "user"-type attribute value stores a
   User.id; a role binding stores a Group.uid. Removing either row would
   cascade those away and erase who owned what, so a disappearance is
   recorded as active=False.
2. A sync only touches rows it owns (matching `source`). A locally
   created group, or a member added by hand, survives it untouched.
3. A person is matched by directory DN first, then by email. Email
   matching is what links a directory entry to someone who already signed
   in through OIDC, so the two never become duplicate people.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.group import Group, GroupMember
from app.models.user import User
from app.services.directory import DirectoryProvider, configured_provider, provider_name


def _match_user(db: Session, dn: str, email: str) -> User | None:
    if dn:
        by_dn = db.scalar(select(User).where(User.dn == dn))
        if by_dn is not None:
            return by_dn
    if email:
        return db.scalar(select(User).where(User.email == email))
    return None


def sync_directory(db: Session, provider: DirectoryProvider | None = None) -> dict:
    provider = provider or configured_provider()
    source = getattr(provider, "name", provider_name())
    now = datetime.now(timezone.utc)

    stats = {
        "provider": source,
        "users_created": 0,
        "users_updated": 0,
        "users_deactivated": 0,
        "groups_created": 0,
        "groups_updated": 0,
        "groups_deactivated": 0,
        "memberships_added": 0,
        "memberships_removed": 0,
    }

    people = provider.people()
    dn_to_user: dict[str, User] = {}

    for person in people:
        user = _match_user(db, person.dn, person.email)
        if user is None:
            user = User(
                id=str(uuid.uuid4()),
                dn=person.dn,
                email=person.email,
                name=person.name,
                username=person.username,
                source=source,
                active=person.active,
                synced_at=now,
            )
            db.add(user)
            db.flush()
            stats["users_created"] += 1
        else:
            # An OIDC user matched by email now gains their directory
            # identity, but keeps their id and their source: they are a real
            # sign-in, not a row this sync invented.
            user.dn = user.dn or person.dn
            user.username = person.username or user.username
            user.name = person.name or user.name
            user.active = person.active
            user.synced_at = now
            stats["users_updated"] += 1
        dn_to_user[person.dn] = user

    # Anyone this source created who is no longer in the directory.
    seen_dns = {p.dn for p in people}
    for stale in db.scalars(
        select(User).where(User.source == source, User.active.is_(True))
    ):
        if stale.dn and stale.dn not in seen_dns:
            stale.active = False
            stale.synced_at = now
            stats["users_deactivated"] += 1

    groups = provider.groups()
    seen_group_dns = {g.dn for g in groups}

    # Membership can be published from either side, and some directories only
    # answer usefully from one of them. INFN's organisational groups list no
    # people at all — only role-qualified subgroups that hold them — while
    # each person's memberOf resolves through that nesting and names the
    # service directly. So both directions are collected and unioned.
    from_person: dict[str, set[str]] = {}
    for person in people:
        user = dn_to_user.get(person.dn)
        if user is None:
            continue
        for group_dn in person.member_of:
            if group_dn in seen_group_dns:
                from_person.setdefault(group_dn, set()).add(user.id)

    for entry in groups:
        group = db.scalar(select(Group).where(Group.dn == entry.dn))
        if group is None:
            group = Group(
                uid=str(uuid.uuid4()),
                dn=entry.dn,
                name=entry.name,
                description=entry.description,
                email=entry.email,
                source=source,
                active=True,
                synced_at=now,
            )
            db.add(group)
            db.flush()
            stats["groups_created"] += 1
        else:
            group.name = entry.name
            group.description = entry.description
            group.email = entry.email
            group.active = True
            group.synced_at = now
            stats["groups_updated"] += 1

        # A member DN that isn't a person we imported is skipped rather than
        # guessed at: in a nested tree it is usually another group, and the
        # people inside it arrive through the memberOf direction instead.
        wanted_user_ids = {
            dn_to_user[member_dn].id
            for member_dn in entry.member_dns
            if member_dn in dn_to_user
        } | from_person.get(entry.dn, set())
        existing = {
            m.user_id: m
            for m in db.scalars(select(GroupMember).where(GroupMember.group_uid == group.uid))
        }
        for user_id in wanted_user_ids - existing.keys():
            db.add(GroupMember(group_uid=group.uid, user_id=user_id, source=source))
            stats["memberships_added"] += 1
        for user_id, membership in existing.items():
            # Only memberships this source created are withdrawn; one added
            # by hand in the app is a deliberate local override.
            if user_id not in wanted_user_ids and membership.source == source:
                db.delete(membership)
                stats["memberships_removed"] += 1

    for stale_group in db.scalars(
        select(Group).where(Group.source == source, Group.active.is_(True))
    ):
        if stale_group.dn and stale_group.dn not in seen_group_dns:
            stale_group.active = False
            stale_group.synced_at = now
            stats["groups_deactivated"] += 1

    db.commit()
    return stats
