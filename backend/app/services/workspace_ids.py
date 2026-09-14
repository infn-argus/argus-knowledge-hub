"""Turning a workspace's name into its identifier.

The identifier goes into URLs, into PAT scopes and into every object key
the imports derive, and it cannot be changed afterwards — so it is worth
having one rule rather than whatever each admin types. The existing ones
were made by hand to the same shape anyway: "EUAPS" became `lnf-euaps`,
"Divisione Acceleratori" became `lnf-divisione-acceleratori`.

The rule is a setting rather than a constant because the prefix is a
local convention: another INFN site would want its own, and hard-coding
`lnf-` would make this installation's habits everyone's.
"""
import re
import unicodedata
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting
from app.models.workspace import Workspace

SETTING_KEY = "workspace_id_rule"

DEFAULTS = {
    # Matches the identifiers this installation already uses.
    "prefix": "",
    "separator": "-",
    "case": "lower",          # "lower" | "upper" | "keep"
    "max_length": 40,
}

# Valid in a URL path segment and in the object keys derived from it.
ALLOWED = re.compile(r"[^A-Za-z0-9]+")


def rule(db: Session) -> dict:
    row = db.get(AppSetting, SETTING_KEY)
    stored = row.value if row is not None and isinstance(row.value, dict) else {}
    return {**DEFAULTS, **stored}


def save_rule(db: Session, values: dict) -> dict:
    row = db.get(AppSetting, SETTING_KEY)
    merged = {**DEFAULTS, **(values or {})}
    if row is None:
        db.add(AppSetting(key=SETTING_KEY, value=merged))
    else:
        row.value = merged
    db.commit()
    return merged


def slugify(name: str, settings: Optional[dict] = None) -> str:
    """`Divisione Acceleratori` -> `divisione-acceleratori`.

    Accents are folded rather than dropped, so "Größe" gives `grosse` and
    not `gre` — a name that loses its letters gives an identifier nobody
    recognises as belonging to it.
    """
    settings = {**DEFAULTS, **(settings or {})}
    separator = str(settings.get("separator") or "-")[:1] or "-"

    folded = unicodedata.normalize("NFKD", str(name or ""))
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = folded.replace("ß", "ss").replace("Ø", "O").replace("ø", "o")

    slug = ALLOWED.sub(separator, folded).strip(separator)
    slug = re.sub(re.escape(separator) + r"{2,}", separator, slug)

    case = settings.get("case") or "lower"
    if case == "lower":
        slug = slug.lower()
    elif case == "upper":
        slug = slug.upper()

    prefix = str(settings.get("prefix") or "")
    if prefix and not slug.startswith(prefix):
        slug = f"{prefix}{slug}"

    limit = int(settings.get("max_length") or 40)
    if limit > 0:
        slug = slug[:limit].strip(separator)
    return slug


def unique_id(db: Session, name: str, settings: Optional[dict] = None) -> str:
    """The identifier this name should get, given what already exists.

    A taken identifier gets a number rather than a failed form: two
    workspaces legitimately called "Test" is a thing that happens, and the
    admin creating the second one should not have to invent a spelling.
    """
    settings = settings or {}
    base = slugify(name, settings)
    if not base:
        # Nothing survived — a name written entirely in a script this
        # folds away. Better a usable identifier than an empty one.
        base = "workspace"

    separator = str(settings.get("separator") or DEFAULTS["separator"])[:1] or "-"
    taken = {
        row for row in db.scalars(select(Workspace.id))
    }
    if base not in taken:
        return base
    for suffix in range(2, 1000):
        candidate = f"{base}{separator}{suffix}"
        if candidate not in taken:
            return candidate
    raise ValueError(f"Could not find a free identifier based on “{base}”.")
