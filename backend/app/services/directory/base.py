from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class DirectoryPerson:
    dn: str
    username: str
    email: str
    name: str | None = None
    active: bool = True
    # Group DNs this person belongs to, when the directory publishes
    # membership from the person's side. INFN's does, and there it is the
    # only usable direction: an organisational group like "Servizio Laser"
    # lists no people at all, only role-qualified subgroups which in turn
    # hold the people — while memberOf resolves through that nesting and
    # names the service directly.
    member_of: list[str] = field(default_factory=list)


@dataclass
class DirectoryGroup:
    dn: str
    name: str
    description: str | None = None
    email: str | None = None
    # Member DNs, not internal ids: a directory describes its own world and
    # the sync is what maps those onto our rows.
    member_dns: list[str] = field(default_factory=list)


class DirectoryProvider(Protocol):
    """Read-only view of an organisation. Implementations must be safe to
    call repeatedly — the sync runs on a schedule and on demand."""

    name: str

    def people(self) -> list[DirectoryPerson]: ...

    def groups(self) -> list[DirectoryGroup]: ...
