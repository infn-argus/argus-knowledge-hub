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
        self.page_size = int(os.environ.get("LDAP_PAGE_SIZE", "500"))

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

    def people(self) -> list[DirectoryPerson]:
        conn = self._connection()
        try:
            out: list[DirectoryPerson] = []
            for entry in self._search(
                conn, self.user_base_dn, self.user_filter,
                [self.attr_username, self.attr_email, self.attr_name],
            ):
                if entry.get("type") != "searchResEntry":
                    continue
                attrs = entry.get("attributes", {})
                username = self._first(attrs, self.attr_username)
                email = self._first(attrs, self.attr_email)
                # A person with neither a username nor an email can't be
                # matched to a sign-in later, so importing them would only
                # create an unreachable row.
                if not username and not email:
                    continue
                out.append(DirectoryPerson(
                    dn=entry["dn"],
                    username=username or (email or "").split("@")[0],
                    email=email or "",
                    name=self._first(attrs, self.attr_name),
                ))
            return out
        finally:
            conn.unbind()

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
                attrs = entry.get("attributes", {})
                name = self._first(attrs, self.attr_group_name)
                if not name:
                    continue
                members = attrs.get(self.attr_group_member) or []
                if not isinstance(members, (list, tuple)):
                    members = [members]
                out.append(DirectoryGroup(
                    dn=entry["dn"],
                    name=name,
                    description=self._first(attrs, self.attr_description),
                    email=self._first(attrs, "mail"),
                    member_dns=[str(m) for m in members],
                ))
            return out
        finally:
            conn.unbind()
