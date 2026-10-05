"""Which AI endpoint a workspace actually uses.

With a workspace per beamline, configuring the same gateway eight times is
eight chances to get it wrong and eight places to rotate a key. So a
workspace with no endpoint of its own falls back to the installation's: the
settings an administrator makes on Administration → AI (the row INSTALLATION),
or, where there are none, the ones configured in a global workspace.

Two things deliberately do not inherit:

`allow_confidential`, because it is a decision about a particular
workspace's documents and nobody made it by ticking a box somewhere else.
A workspace running on the shared default sends nothing marked riservato.

An unchecked or disabled default, because inheriting a broken endpoint
just moves the failure to the point of use, which is what the check exists
to prevent.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.llm_config import LLMConfig
from app.models.workspace import Workspace


# The installation's own settings: an llm_configs row no workspace can be named after.
INSTALLATION = "__installation__"


def installation_config(db: Session) -> Optional[LLMConfig]:
    return db.get(LLMConfig, INSTALLATION)


def installation_problem(db: Session) -> Optional[str]:
    """Why the installation's settings are not being shared, or None when they are (or there are none)."""
    mine = installation_config(db)
    if mine is None:
        return None
    if not mine.enabled:
        return ("The installation's AI settings (Administration → AI) are switched off: tick “Offer AI "
                "features to the workspaces that use these settings”, save, and check the endpoint.")
    if mine.last_check_ok is None:
        return ("The installation's AI settings (Administration → AI) have not been checked since they were "
                "last saved: press “Check endpoint” there.")
    if not mine.last_check_ok:
        return ("The installation's AI settings (Administration → AI) failed their last check"
                + (f": {mine.last_check_error}" if mine.last_check_error else "."))
    return None


def own_config(db: Session, workspace_id: str) -> Optional[LLMConfig]:
    """This workspace's own settings, inherited or not."""
    return db.get(LLMConfig, workspace_id)


def default_config(db: Session) -> Optional[LLMConfig]:
    """The shared endpoint: the one configured in a global workspace.

    There is one global workspace in practice. Where there are several, the
    first *that has a usable endpoint* wins, by id — taking the first global
    workspace and giving up when it happens to have no AI configured would
    make the shared default depend on a name. The installation's own settings
    (Administration → AI), when usable, come before any of them.
    """
    mine = installation_config(db)
    if mine is not None and mine.enabled and mine.last_check_ok:
        return mine
    for workspace in db.scalars(
        select(Workspace).where(Workspace.is_global.is_(True)).order_by(Workspace.id)
    ):
        config = db.get(LLMConfig, workspace.id)
        if config is not None and config.enabled and config.last_check_ok:
            return config
    return None


def resolve(db: Session, workspace_id: str) -> tuple[Optional[LLMConfig], Optional[str]]:
    """The endpoint this workspace should use, and where it came from.

    The second value is the workspace the settings belong to when they were
    inherited, and None when they are the caller's own — so a page can say
    "using the shared endpoint" instead of showing settings nobody here set.
    """
    config = own_config(db, workspace_id)
    if config is not None:
        return config, None

    shared = default_config(db)
    if shared is None:
        return None, None
    if shared.workspace_id == workspace_id:
        return shared, None

    # A copy, never added to the session: handing back the global row would
    # let a caller read allow_confidential from a decision made elsewhere,
    # and any stray mutation would be written to the shared configuration.
    borrowed = LLMConfig(
        workspace_id=workspace_id,
        base_url=shared.base_url,
        model=shared.model,
        embedding_model=shared.embedding_model,
        vision_model=shared.vision_model,
        asr_model=shared.asr_model,
        tts_model=shared.tts_model,
        rerank_model=shared.rerank_model,
        encrypted_secret=shared.encrypted_secret,
        enabled=shared.enabled,
        allow_confidential=False,
        # The gateway's limit, not a decision about this workspace's data: it comes along.
        max_output_tokens=shared.max_output_tokens,
        last_checked_at=shared.last_checked_at,
        last_check_ok=shared.last_check_ok,
        last_check_error=shared.last_check_error,
    )
    return borrowed, shared.workspace_id
