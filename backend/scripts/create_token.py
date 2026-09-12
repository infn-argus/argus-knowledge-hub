"""Admin script: create a workspace (if needed) and mint a bearer token for it.

Usage: python scripts/create_token.py <workspace_id> <workspace_name> [token_label]
Prints the plaintext token once. It is not recoverable afterwards — store it
the same way you'd store a GitHub PAT.
"""
import secrets
import sys

sys.path.insert(0, ".")

from app.auth import hash_token  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models.api_token import ApiToken  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    workspace_id, workspace_name = sys.argv[1], sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else None

    db = SessionLocal()
    try:
        if db.get(Workspace, workspace_id) is None:
            db.add(Workspace(id=workspace_id, name=workspace_name))
            db.flush()

        raw_token = secrets.token_urlsafe(32)
        db.add(
            ApiToken(
                workspace_id=workspace_id,
                token_hash=hash_token(raw_token),
                label=label,
            )
        )
        db.commit()
    finally:
        db.close()

    print(f"Workspace: {workspace_id}")
    print(f"Token (save this now, it will not be shown again):\n{raw_token}")


if __name__ == "__main__":
    main()
