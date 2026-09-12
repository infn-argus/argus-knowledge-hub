from typing import Optional

from sqlalchemy.orm import Session

from app.models.schema import Schema
from app.services.attribute_validation import effective_attributes


def stamp_current_user_attributes(
    db: Session,
    schema: Optional[Schema],
    attributes: dict,
    user_id: Optional[str],
) -> None:
    """Overwrite every "current_user"-type attribute with the acting user's
    id, in place. Runs on every create *and* update — this is a "last set
    by" field, not a "created by" one, per how it's meant to be used. A
    PAT-driven write (no person behind it) clears the field to None rather
    than leaving a stale value."""
    if schema is None:
        return
    for attr in effective_attributes(db, schema):
        if attr.get("type") != "current_user":
            continue
        key = attr.get("key") or attr.get("name")
        if not key:
            continue
        attributes[key] = [user_id] if attr.get("multiValue") else user_id
