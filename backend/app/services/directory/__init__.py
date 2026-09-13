"""Where people and groups come from.

Authentication stays with OIDC — the directory is only asked *who exists*
and *who belongs to what*, never to verify a password. That keeps INFN
credentials out of this application entirely, and means the switch to
Keycloak-supplied group claims replaces this module's source without
touching anything that consumes it.
"""
from app.services.directory.base import DirectoryGroup, DirectoryPerson, DirectoryProvider
from app.services.directory.embedded import EmbeddedDirectory
from app.services.directory.provider import configured_provider, provider_name

__all__ = [
    "DirectoryGroup",
    "DirectoryPerson",
    "DirectoryProvider",
    "EmbeddedDirectory",
    "configured_provider",
    "provider_name",
]
