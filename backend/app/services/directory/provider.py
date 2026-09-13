import os

from app.services.directory.base import DirectoryProvider
from app.services.directory.embedded import EmbeddedDirectory
from app.services.directory.ldap import LdapDirectory, ldap_configured


def provider_name() -> str:
    """Which directory this instance is using. Surfaced in the API so an
    operator can tell at a glance whether they are looking at real people
    or at the built-in test organisation."""
    explicit = os.environ.get("DIRECTORY_PROVIDER")
    if explicit:
        return explicit
    return "ldap" if ldap_configured() else "embedded"


def configured_provider() -> DirectoryProvider:
    name = provider_name()
    if name == "ldap":
        if not ldap_configured():
            raise RuntimeError(
                "DIRECTORY_PROVIDER=ldap but LDAP_URL is not set — refusing to "
                "fall back to the embedded test directory, which would put "
                "fictional people in front of real users."
            )
        return LdapDirectory()
    if name == "embedded":
        return EmbeddedDirectory()
    raise RuntimeError(f"Unknown DIRECTORY_PROVIDER {name!r} (expected 'ldap' or 'embedded')")
