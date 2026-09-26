"""Which recorded objects a piece of text actually mentions.

Deliberately not a model's job. Asking a model which equipment a document
refers to invites a confident answer about a magnet that does not exist,
and a wrong edge in the knowledge graph is worse than a missing one — it
is a fact the graph will happily repeat.

So the text is matched against the inventory: an object key is a key, and
a name that appears in the prose is a name. What comes back is a list of
things that are certainly there.
"""
import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset

# The shape an object key takes here: letters, a hyphen, digits.
KEY_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,8}\b")

# Shorter names match too much — "PLC", "Rack" and "Cam" appear in prose
# that has nothing to do with a particular object.
MIN_NAME_LENGTH = 6


def objects_mentioned(db: Session, workspace_id: str, *texts: str) -> list[dict]:
    """Objects this text names, by key or by name.

    Each result says which it was, because the two are not equally strong:
    a key is an identifier somebody wrote down deliberately, a name could
    be a coincidence of words.
    """
    haystack = "\n".join(t for t in texts if t)
    if not haystack.strip():
        return []
    upper = haystack.upper()

    assets: Iterable[Asset] = db.scalars(
        select(Asset).where(Asset.workspace_id == workspace_id)
    )

    found: dict[str, dict] = {}
    keys_in_text = set(KEY_PATTERN.findall(upper))

    from app.services.visibility import can_see
    for asset in assets:
        # A restricted record is never named to someone without its grant (I-ACL-1).
        if not can_see(asset):
            continue
        if asset.key and asset.key.upper() in keys_in_text:
            found[asset.uid] = {
                "uid": asset.uid,
                "key": asset.key,
                "name": asset.name,
                "matched_on": "key",
            }
            continue
        name = (asset.name or "").strip()
        if len(name) >= MIN_NAME_LENGTH and name.upper() in upper:
            found.setdefault(asset.uid, {
                "uid": asset.uid,
                "key": asset.key,
                "name": asset.name,
                "matched_on": "name",
            })

    # Keys first: they are the stronger evidence.
    return sorted(found.values(), key=lambda row: (row["matched_on"] != "key", row["name"] or ""))
