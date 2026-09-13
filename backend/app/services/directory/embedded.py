"""A directory with no server behind it.

Used when no LDAP is configured, so a developer, a test, or a demo
instance has a realistic organisation to work against: role bindings,
group-typed attributes and assignment pickers all need people and groups
to exist before any of them can be exercised.

The shape mirrors the real LNF one — services under a division, plus a
couple of cross-cutting bodies — because the interesting cases (a person
in several groups, a group with no members, an inactive account) only
show up with that shape. Every row is marked source="embedded" so it is
obvious in the UI and so a later LDAP sync leaves it alone.
"""
from app.services.directory.base import DirectoryGroup, DirectoryPerson

BASE = "dc=lnf,dc=infn,dc=it"


def _person(uid: str, name: str, active: bool = True) -> DirectoryPerson:
    return DirectoryPerson(
        dn=f"uid={uid},ou=people,{BASE}",
        username=uid,
        email=f"{uid}@lnf.infn.it",
        name=name,
        active=active,
    )


def _group(cn: str, name: str, description: str, members: list[str]) -> DirectoryGroup:
    return DirectoryGroup(
        dn=f"cn={cn},ou=groups,{BASE}",
        name=name,
        description=description,
        email=f"{cn}@lnf.infn.it",
        member_dns=[f"uid={uid},ou=people,{BASE}" for uid in members],
    )


PEOPLE: list[DirectoryPerson] = [
    _person("amichelotti", "Andrea Michelotti"),
    _person("gbianchi", "Giulia Bianchi"),
    _person("mrossi", "Marco Rossi"),
    _person("lferrari", "Laura Ferrari"),
    _person("proberti", "Paolo Roberti"),
    _person("sconti", "Sara Conti"),
    _person("dgreco", "Davide Greco"),
    # Someone who has left: the sync has to deactivate rather than delete,
    # since their name is still on past tickets and history entries.
    _person("fvitale", "Francesca Vitale", active=False),
]

GROUPS: list[DirectoryGroup] = [
    _group(
        "divisione-acceleratori", "Divisione Acceleratori",
        "Accelerator Division — covers every service below",
        ["amichelotti", "gbianchi", "mrossi", "lferrari", "proberti", "sconti", "dgreco"],
    ),
    _group("servizio-laser", "Servizio Laser", "Laser systems",
           ["amichelotti", "gbianchi"]),
    _group("servizio-vuoto", "Servizio Vuoto", "Vacuum systems",
           ["mrossi", "lferrari"]),
    _group("servizio-criogenia", "Servizio Criogenia", "Cryogenics",
           ["proberti"]),
    _group("servizio-controlli", "Servizio Controlli", "Control systems",
           ["amichelotti", "dgreco"]),
    _group("euaps-operations", "EUAPS Operations", "EUAPS run coordination",
           ["gbianchi", "sconti"]),
    # A body that exists before anyone is assigned to it — the empty-group
    # case a picker and a role binding both have to survive.
    _group("documentation-board", "Documentation Board",
           "Approves controlled documentation", []),
]


class EmbeddedDirectory:
    name = "embedded"

    def people(self) -> list[DirectoryPerson]:
        return list(PEOPLE)

    def groups(self) -> list[DirectoryGroup]:
        return list(GROUPS)
