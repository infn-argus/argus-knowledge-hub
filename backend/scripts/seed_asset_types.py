"""Admin script: seed the object type catalogue into a workspace.

Creates the ~100 accelerator object types (Quadrupole, Ion Pump, Screen
Station, IOC, ...) in one workspace, or brings a workspace that already has
them up to date. Safe to run again: existing types keep every attribute they
have and gain any they lack, and types the EPIK8s importers made are adopted
rather than duplicated. Run it before or after an import; the result is the
same.

It is a script, not part of creating a workspace, on purpose: a workspace that
only holds tickets has no use for a hundred object types in its tree.

Usage (from anywhere, with the backend's virtualenv and DATABASE_URL set):
  python backend/scripts/seed_asset_types.py <workspace_id> [--dry-run]
"""
import os
import sys

# Runs from any directory: the app package is next to scripts/, not next to
# wherever the shell happens to be.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv[1:]
    if len(args) != 1:
        print(__doc__)
        sys.exit(1)
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set, e.g. "
              "postgresql://postgres:postgres@localhost:5432/app")
        sys.exit(1)

    from app.db import SessionLocal
    from app.models.workspace import Workspace
    from app.services.asset_types import ensure_asset_types

    db = SessionLocal()
    try:
        if db.get(Workspace, args[0]) is None:
            print(f"No workspace {args[0]!r}.")
            sys.exit(1)
        result = ensure_asset_types(db, args[0])
        print(f"created {len(result.created)}, adopted {len(result.adopted)}, "
              f"extended {len(result.extended)}")
        if result.adopted:
            print("  adopted (made by an importer, now under the catalogue): "
                  + ", ".join(result.adopted))
        if result.duplicates:
            print("  already had a type of the same name that is not the catalogue's — "
                  "left alone, and now there are two: " + ", ".join(result.duplicates))
        if dry_run:
            db.rollback()
            print("dry run: nothing written.")
        else:
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
