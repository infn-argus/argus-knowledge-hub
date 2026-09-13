"""Shaping of real INFN directory entries.

Every fixture below is a genuine entry from ds.infn.it, reduced to the
attributes the provider reads. The tree is not what the defaults assume:

* a group's cn is an opaque code ("1_352") and its meaning lives in
  description as a path ending in the real name ("...->Servizio Laser");
* organisational groups contain no people at all — only role-qualified
  subgroups ("::Nomina:Member") which hold them — so reading `member`
  alone yields groups that all look empty;
* memberOf on a person resolves through that nesting and names the
  service directly, which is why membership is read from the person.
"""
import secrets

import pytest
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models.group import Group, GroupMember
from app.models.user import User
from app.models.workspace import Workspace
from app.services.directory.base import DirectoryGroup
from app.services.directory.ldap import LdapDirectory
from app.services.directory_sync import sync_directory

BASE = "dc=infn,dc=it"
LNF = "Istituzioni->INFN->Laboratori Nazionali di Frascati"

# Real entries, member lists truncated.
SERVIZIO_LASER = {
    "dn": f"cn=1_352,ou=Groups,{BASE}",
    "attrs": {
        "cn": ["1_352"],
        "description": [f"{LNF}->Divisione Acceleratori->Servizio Laser"],
        "member": [f"cn=1_352_5_8387,ou=Groups,{BASE}", f"cn=1_352_3_2,ou=Groups,{BASE}"],
    },
}
SERVIZIO_LASER_NOMINA = {
    "dn": f"cn=1_352_5_8387,ou=Groups,{BASE}",
    "attrs": {
        "cn": ["1_352_5_8387"],
        "description": [f"{LNF}->Divisione Acceleratori->Servizio Laser::Nomina:Member"],
        "member": [f"infnUUID=aaa,ou=People,{BASE}"],
    },
}
PERSON = {
    "dn": f"infnUUID=f6a87c4d,ou=People,{BASE}",
    "attrs": {
        "uid": ["amichelo"],
        "mail": ["andrea.michelotti@infn.it"],
        "cn": ["Andrea Michelotti"],
        "memberOf": [
            f"cn=1_352,ou=Groups,{BASE}",           # the service itself
            f"cn=1_352_5_8387,ou=Groups,{BASE}",    # the role group inside it
            f"cn=166_2,ou=Groups,{BASE}",           # an unrelated access group
        ],
    },
}


@pytest.fixture()
def infn_directory(monkeypatch):
    """The provider configured the way the INFN tree needs."""
    monkeypatch.setenv("LDAP_URL", "ldaps://ds.infn.it")
    monkeypatch.setenv("LDAP_USER_BASE_DN", f"ou=People,{BASE}")
    monkeypatch.setenv("LDAP_GROUP_BASE_DN", f"ou=Groups,{BASE}")
    monkeypatch.setenv("LDAP_ATTR_GROUP_NAME", "description")
    monkeypatch.setenv("LDAP_GROUP_PATH_SEPARATOR", "->")
    monkeypatch.setenv("LDAP_GROUP_EXCLUDE_SUBSTRING", "::")
    return LdapDirectory()


def test_group_name_is_the_last_path_segment(infn_directory):
    group = infn_directory.group_from_entry(SERVIZIO_LASER["dn"], SERVIZIO_LASER["attrs"])
    assert group is not None
    assert group.name == "Servizio Laser"
    # The full path stays, so two services of the same name under different
    # divisions remain distinguishable.
    assert group.description.endswith("Divisione Acceleratori->Servizio Laser")
    assert group.description.startswith("Istituzioni->INFN")


def test_role_qualified_duplicates_are_skipped(infn_directory):
    """Without this, every service would appear several times over —
    once as itself, then as member, head and guest."""
    assert infn_directory.group_from_entry(
        SERVIZIO_LASER_NOMINA["dn"], SERVIZIO_LASER_NOMINA["attrs"]
    ) is None


def test_person_membership_is_read_from_member_of(infn_directory):
    person = infn_directory.person_from_entry(PERSON["dn"], PERSON["attrs"])
    assert person is not None
    assert person.username == "amichelo"
    assert person.email == "andrea.michelotti@infn.it"
    assert person.name == "Andrea Michelotti"
    assert f"cn=1_352,ou=Groups,{BASE}" in person.member_of


def test_defaults_still_suit_a_plain_directory(monkeypatch):
    """A conventional tree — cn as the name, people directly in member —
    must keep working untouched."""
    monkeypatch.setenv("LDAP_URL", "ldaps://example.invalid")
    monkeypatch.setenv("LDAP_USER_BASE_DN", "ou=people,dc=example")
    monkeypatch.setenv("LDAP_GROUP_BASE_DN", "ou=groups,dc=example")
    for leftover in ("LDAP_ATTR_GROUP_NAME", "LDAP_GROUP_PATH_SEPARATOR",
                     "LDAP_GROUP_EXCLUDE_SUBSTRING"):
        monkeypatch.delenv(leftover, raising=False)

    directory = LdapDirectory()
    group = directory.group_from_entry("cn=laser,ou=groups,dc=example", {
        "cn": ["laser"], "description": ["Laser systems"],
        "member": ["uid=a,ou=people,dc=example"],
    })
    assert group.name == "laser"
    assert group.description == "Laser systems"
    assert group.member_dns == ["uid=a,ou=people,dc=example"]


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


def test_sync_populates_a_group_that_lists_no_people():
    """The shape that would otherwise produce 144 empty groups: the service
    group's own member list holds only subgroups, and the people arrive
    through memberOf."""
    suffix = secrets.token_hex(4)
    laser_dn = f"cn=1_352-{suffix},ou=Groups,{BASE}"

    class InfnLike:
        name = "ldap"

        def people(self):
            from app.services.directory.base import DirectoryPerson

            return [
                DirectoryPerson(
                    dn=f"infnUUID=p1-{suffix},ou=People,{BASE}",
                    username=f"p1-{suffix}", email=f"p1-{suffix}@infn.it",
                    name="Person One", member_of=[laser_dn],
                ),
                DirectoryPerson(
                    dn=f"infnUUID=p2-{suffix},ou=People,{BASE}",
                    username=f"p2-{suffix}", email=f"p2-{suffix}@infn.it",
                    name="Person Two", member_of=[laser_dn],
                ),
            ]

        def groups(self):
            return [DirectoryGroup(
                dn=laser_dn, name="Servizio Laser",
                description=f"{LNF}->Divisione Acceleratori->Servizio Laser",
                # Only subgroups, exactly as the real entry has.
                member_dns=[f"cn=1_352_5_8387-{suffix},ou=Groups,{BASE}"],
            )]

    db = SessionLocal()
    db.add(Workspace(id=f"ws-{suffix}", name="WS"))
    db.commit()

    stats = sync_directory(db, InfnLike())
    assert stats["users_created"] == 2
    assert stats["groups_created"] == 1
    assert stats["memberships_added"] == 2, "people must arrive via memberOf"

    group = db.scalar(select(Group).where(Group.dn == laser_dn))
    members = db.scalars(select(GroupMember).where(GroupMember.group_uid == group.uid)).all()
    assert len(members) == 2
    emails = {db.get(User, m.user_id).email for m in members}
    assert emails == {f"p1-{suffix}@infn.it", f"p2-{suffix}@infn.it"}
    db.close()
