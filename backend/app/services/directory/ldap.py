"""LDAP as a read-only directory.

Binds once with a service account and reads; it never binds as an end
user, because authentication belongs to OIDC and this application should
never see an INFN password.

Every attribute name is configurable: INFN's tree is not guaranteed to
use the same names as the defaults below, and a wrong guess is a config
change rather than a release.
"""
import os

from app.services.directory.base import DirectoryGroup, DirectoryPerson


def ldap_configured() -> bool:
    return bool(os.environ.get("LDAP_URL"))


class LdapDirectory:
    name = "ldap"

    def __init__(self) -> None:
        self.url = os.environ["LDAP_URL"]
        self.bind_dn = os.environ.get("LDAP_BIND_DN") or None
        self.bind_password = os.environ.get("LDAP_BIND_PASSWORD") or None
        self.user_base_dn = os.environ["LDAP_USER_BASE_DN"]
        self.user_filter = os.environ.get("LDAP_USER_FILTER", "(objectClass=inetOrgPerson)")
        self.group_base_dn = os.environ["LDAP_GROUP_BASE_DN"]
        self.group_filter = os.environ.get("LDAP_GROUP_FILTER", "(objectClass=groupOfNames)")
        self.attr_username = os.environ.get("LDAP_ATTR_USERNAME", "uid")
        self.attr_email = os.environ.get("LDAP_ATTR_EMAIL", "mail")
        self.attr_name = os.environ.get("LDAP_ATTR_NAME", "cn")
        self.attr_group_name = os.environ.get("LDAP_ATTR_GROUP_NAME", "cn")
        self.attr_group_member = os.environ.get("LDAP_ATTR_GROUP_MEMBER", "member")
        self.attr_description = os.environ.get("LDAP_ATTR_DESCRIPTION", "description")
        self.attr_member_of = os.environ.get("LDAP_ATTR_MEMBER_OF", "memberOf")
        self.page_size = int(os.environ.get("LDAP_PAGE_SIZE", "500"))
        # INFN's tree names a group by an opaque code in cn ("1_352") and puts
        # the meaning in description as a path:
        #   Istituzioni->INFN->Laboratori Nazionali di Frascati->
        #   Divisione Acceleratori->Servizio Laser
        # With a separator configured, the last segment becomes the display
        # name and the whole path is kept as the description — so a picker
        # reads "Servizio Laser" instead of ninety characters of ancestry,
        # and the full path is still there to disambiguate two services of
        # the same name under different divisions.
        self.group_path_separator = os.environ.get("LDAP_GROUP_PATH_SEPARATOR", "")
        # Same tree carries role-qualified duplicates of each group
        # ("...->Servizio Laser::Nomina:Responsabile"), which would otherwise
        # show up as several groups with the same display name meaning
        # member, head and guest.
        self.group_exclude = os.environ.get("LDAP_GROUP_EXCLUDE_SUBSTRING", "")

    def _connection(self):
        # Imported lazily so an instance with no LDAP configured doesn't need
        # the dependency resolved at import time.
        from ldap3 import ALL, Connection, Server

        server = Server(self.url, get_info=ALL)
        return Connection(
            server,
            user=self.bind_dn,
            password=self.bind_password,
            auto_bind=True,
            raise_exceptions=True,
        )

    @staticmethod
    def _first(entry, attribute: str) -> str | None:
        values = entry.get(attribute)
        if not values:
            return None
        if isinstance(values, (list, tuple)):
            return str(values[0]) if values else None
        return str(values)

    def _search(self, conn, base_dn: str, search_filter: str, attributes: list[str]):
        return conn.extend.standard.paged_search(
            search_base=base_dn,
            search_filter=search_filter,
            attributes=attributes,
            paged_size=self.page_size,
            generator=True,
        )

    def person_from_entry(self, dn: str, attrs: dict) -> DirectoryPerson | None:
        username = self._first(attrs, self.attr_username)
        email = self._first(attrs, self.attr_email)
        # Someone with neither a username nor an email can't be matched to a
        # sign-in later, so importing them would only create an unreachable
        # row.
        if not username and not email:
            return None
        member_of = attrs.get(self.attr_member_of) or []
        if not isinstance(member_of, (list, tuple)):
            member_of = [member_of]
        return DirectoryPerson(
            dn=dn,
            username=username or (email or "").split("@")[0],
            email=email or "",
            name=self._first(attrs, self.attr_name),
            member_of=[str(g) for g in member_of],
        )

    def people(self) -> list[DirectoryPerson]:
        conn = self._connection()
        try:
            out: list[DirectoryPerson] = []
            for entry in self._search(
                conn, self.user_base_dn, self.user_filter,
                [self.attr_username, self.attr_email, self.attr_name, self.attr_member_of],
            ):
                if entry.get("type") != "searchResEntry":
                    continue
                person = self.person_from_entry(entry["dn"], entry.get("attributes", {}))
                if person is not None:
                    out.append(person)
            return out
        finally:
            conn.unbind()

    def group_from_entry(self, dn: str, attrs: dict) -> DirectoryGroup | None:
        """Turn one directory entry into a group, or None to skip it.

        Kept separate from the search so it can be exercised against
        captured real entries without a server.
        """
        name = self._first(attrs, self.attr_group_name)
        if not name:
            return None
        description = self._first(attrs, self.attr_description)

        if self.group_exclude and (
            self.group_exclude in name or self.group_exclude in (description or "")
        ):
            return None

        if self.group_path_separator and self.group_path_separator in name:
            # The full path is the more useful description; whatever the
            # description attribute held is usually the same string anyway.
            description = name
            name = name.rsplit(self.group_path_separator, 1)[-1].strip()
            if not name:
                return None

        members = attrs.get(self.attr_group_member) or []
        if not isinstance(members, (list, tuple)):
            members = [members]
        return DirectoryGroup(
            dn=dn,
            name=name,
            description=description,
            email=self._first(attrs, "mail"),
            member_dns=[str(m) for m in members],
        )

    def groups(self) -> list[DirectoryGroup]:
        conn = self._connection()
        try:
            out: list[DirectoryGroup] = []
            for entry in self._search(
                conn, self.group_base_dn, self.group_filter,
                [self.attr_group_name, self.attr_group_member, self.attr_description, "mail"],
            ):
                if entry.get("type") != "searchResEntry":
                    continue
                group = self.group_from_entry(entry["dn"], entry.get("attributes", {}))
                if group is not None:
                    out.append(group)
            return out
        finally:
            conn.unbind()
