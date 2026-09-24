from datetime import datetime
from typing import Optional

MERGE_STRATEGIES = ("override", "no_override", "update_if_newer")

# Strategies that used to exist and are no longer honoured. "remove_all_before"
# deleted every previously imported record before re-importing, which cascaded
# to ticket links, relations and history: an import must never destroy what
# people attached to a record (docs/asset-model-revision.md, §11). A stored
# configuration that still names it runs as "override" and says so.
RETIRED_STRATEGIES = {
    "remove_all_before": (
        "The \"remove all before\" strategy is retired: nothing was deleted. "
        "This run updated records in place (override); records the source no "
        "longer contains are left for review instead of being removed."
    ),
}


def effective_strategy(strategy: str) -> tuple[str, Optional[str]]:
    """The strategy a run actually uses, and a note when it differs from the
    one requested because that one is retired."""
    note = RETIRED_STRATEGIES.get(strategy)
    return ("override", note) if note else (strategy, None)


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
    # "override".
    return True
