"""LDAP as a read-only directory.

Binds once with a service account and reads; it never binds as an end
user, because authentication belongs to OIDC and this application should
never see an INFN password.

Every attribute name is configurable: INFN's tree is not guaranteed to
use the same names as the defaults below, and a wrong guess is a config
change rather than a release.
"""
import logging
import os
from contextlib import contextmanager

from app.services.directory.base import DirectoryGroup, DirectoryPerson

logger = logging.getLogger(__name__)


def ldap_configured() -> bool:
    return bool(os.environ.get("LDAP_URL"))


REVERSE_DNS_MODES = ("off", "optional", "require", "ip-only")
CHANNEL_BINDING_MODES = ("auto", "on", "off")


@contextmanager
def _channel_bindings(enabled: bool):
    """Turn the TLS channel-binding token on or off for one bind.

    ldap3 offers no per-connection setting, so the module function has to be
    swapped and put back. Kept as narrow as possible: it is a process-wide
    global for the duration of the bind, which matters only if two binds run
    concurrently with different settings — the directory sync is a single
    sequential job, so they don't.
    """
    import ldap3.protocol.sasl.kerberos as kerberos_sasl

    if enabled:
        yield
        return
    original = kerberos_sasl.get_channel_bindings
    kerberos_sasl.get_channel_bindings = lambda _socket: None
    try:
        yield
    finally:
        kerberos_sasl.get_channel_bindings = original


class LdapDirectory:
    name = "ldap"

    def __init__(self) -> None:
        self.url = os.environ["LDAP_URL"]
        self.bind_dn = os.environ.get("LDAP_BIND_DN") or None
        self.bind_password = os.environ.get("LDAP_BIND_PASSWORD") or None
        # "gssapi" binds with a Kerberos service principal instead of a
        # password — the idiomatic choice against a Kerberos-backed
        # directory like INFN's, and it means no password exists to leak or
        # rotate by hand. Inferred from the keytab so a deployment that
        # mounts one doesn't also have to remember a flag.
        self.keytab = os.environ.get("LDAP_KEYTAB") or None
        self.auth = (os.environ.get("LDAP_AUTH") or ("gssapi" if self.keytab else "simple")).lower()
        # Pin the host the service ticket is requested for, when reverse DNS
        # can't be relied on.
        self.sasl_hostname = os.environ.get("LDAP_SASL_HOSTNAME") or None
        self.sasl_reverse_dns = (os.environ.get("LDAP_SASL_REVERSE_DNS") or "optional").lower()
        if self.sasl_reverse_dns not in REVERSE_DNS_MODES:
            raise RuntimeError(
                f"LDAP_SASL_REVERSE_DNS must be one of {REVERSE_DNS_MODES}, "
                f"got {self.sasl_reverse_dns!r}"
            )
        self.sasl_channel_binding = (
            os.environ.get("LDAP_SASL_CHANNEL_BINDING") or "auto"
        ).lower()
        if self.sasl_channel_binding not in CHANNEL_BINDING_MODES:
            raise RuntimeError(
                f"LDAP_SASL_CHANNEL_BINDING must be one of {CHANNEL_BINDING_MODES}, "
                f"got {self.sasl_channel_binding!r}"
            )
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
        if self.auth == "gssapi":
            from ldap3 import KERBEROS, SASL
            from ldap3.core.rdns import ReverseDnsSetting

            if self.keytab:
                # MIT Kerberos acquires initial credentials from this keytab
                # on its own when none are cached, and re-acquires them once
                # they expire — so a long-lived process needs no kinit and no
                # ticket-renewal loop of our own.
                os.environ.setdefault("KRB5_CLIENT_KTNAME", self.keytab)

            # Which host the Kerberos service ticket is asked for. ds.infn.it
            # is a round-robin alias and the ldap/... principal is registered
            # under the real host, so asking for the alias fails with "Server
            # not found in Kerberos database". ldapsearch succeeds because it
            # canonicalises the peer address through reverse DNS by default;
            # ldap3 does not, unless told to here.
            if self.sasl_hostname:
                sasl_credentials = (self.sasl_hostname,)
            else:
                sasl_credentials = ({
                    "off": ReverseDnsSetting.OFF,
                    "optional": ReverseDnsSetting.OPTIONAL_RESOLVE_ALL_ADDRESSES,
                    "require": ReverseDnsSetting.REQUIRE_RESOLVE_ALL_ADDRESSES,
                    "ip-only": ReverseDnsSetting.REQUIRE_RESOLVE_IP_ADDRESSES_ONLY,
                }[self.sasl_reverse_dns],)

            def connect(channel_binding: bool):
                with _channel_bindings(channel_binding):
                    return Connection(
                        server,
                        authentication=SASL,
                        sasl_mechanism=KERBEROS,
                        sasl_credentials=sasl_credentials,
                        auto_bind=True,
                        raise_exceptions=True,
                    )

            if self.sasl_channel_binding in ("on", "off"):
                return connect(self.sasl_channel_binding == "on")

            # "auto": ldap3 sends a TLS channel-binding token that 389
            # Directory Server rejects, and the bind then fails with a bare
            # "invalidCredentials" that says nothing about why. Rather than
            # leave every deployment to discover that, try the strict way and
            # fall back once. Both attempts use the same credentials, so a
            # genuinely wrong one still fails.
            from ldap3.core.exceptions import LDAPInvalidCredentialsResult

            try:
                return connect(True)
            except LDAPInvalidCredentialsResult:
                logger.info(
                    "LDAP GSSAPI bind refused with channel binding; retrying without it. "
                    "Set LDAP_SASL_CHANNEL_BINDING=off to skip the first attempt."
                )
                return connect(False)
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
