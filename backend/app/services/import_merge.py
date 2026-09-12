from datetime import datetime
from typing import Optional

MERGE_STRATEGIES = ("override", "no_override", "update_if_newer", "remove_all_before")


def should_write(
    strategy: str,
    is_new: bool,
    local_updated_at: Optional[datetime],
    source_updated_at: Optional[datetime],
) -> bool:
    """Whether an already-imported object's fields should be overwritten
    this run. A brand-new object is always written regardless of strategy."""
    if is_new:
        return True
    if strategy == "no_override":
        return False
    if strategy == "update_if_newer":
        if source_updated_at is None or local_updated_at is None:
            # Can't compare — fall back to writing rather than silently
            # dropping data we can't prove is stale.
            return True
        return source_updated_at > local_updated_at
    # "override" and "remove_all_before" (everything is new right after the
    # wipe, but this also covers any row that manages to survive it).
    return True
