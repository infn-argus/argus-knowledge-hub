"""Admin script: read an engineering breakdown (PBS) workbook into a workspace.

Every component row becomes an object of the catalogue type its component
code names, with the utilities it needs and what it costs kept as records of
their own, linked to it. The types are seeded first if they are not there:
with --catalogue the shared ones are used where they are and only this
beamline's own are created here; without it the whole catalogue is seeded into
the workspace. Safe to run again: it updates what the workbook says and
leaves whatever anybody has added since.

--facility prefixes every object key, because keys are unique across the whole
installation. --dry-run reads and reports without writing.

Usage (from anywhere, with the backend's virtualenv and DATABASE_URL set):
  python backend/scripts/import_pbs.py <workspace_id> <workbook.xlsx> --facility EUAP
      [--catalogue <catalogue_workspace>] [--dry-run]
"""
import os
import sys

# Runs from any directory: the app package is next to scripts/, not next to
# wherever the shell happens to be.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    argv = sys.argv[1:]
    dry_run = "--dry-run" in argv
    facility = argv[argv.index("--facility") + 1] if "--facility" in argv else None
    catalogue = argv[argv.index("--catalogue") + 1] if "--catalogue" in argv else None
    rest = [a for i, a in enumerate(argv)
            if not a.startswith("--") and not (i and argv[i - 1] in ("--facility", "--catalogue"))]
    if len(rest) != 2 or not facility:
        print(__doc__)
        sys.exit(1)
    workspace_id, path = rest
    if not os.path.exists(path):
        print(f"No such file: {path}")
        sys.exit(1)
    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set, e.g. "
              "postgresql://postgres:postgres@localhost:5432/app")
        sys.exit(1)

    from app.db import SessionLocal
    from app.models.workspace import Workspace
    from app.services.pbs_import import import_pbs, read_workbook

    book = read_workbook(path)
    print(f"read {len(book.components)} components, {len(book.work_packages)} work packages, "
          f"{len(book.zones)} zones, {len(book.areas)} areas")
    db = SessionLocal()
    try:
        if db.get(Workspace, workspace_id) is None:
            print(f"No workspace {workspace_id!r}.")
            sys.exit(1)
        try:
            result = import_pbs(db, workspace_id, book, facility, path.rsplit("/", 1)[-1],
                                dry_run, catalogue_workspace_id=catalogue)
        except ValueError as e:                    # includes CatalogueMissing
            print(e)
            sys.exit(1)
    finally:
        db.close()
    for name, n in sorted(result.counts.items()):
        print(f"  {name:22s} {n}")
    for note in result.seeded:
        print(f"  ({note} first)")
    if result.warnings:
        print(f"{len(result.warnings)} warning(s):")
        for w in result.warnings:
            print("  - " + w)
    print("dry run: nothing written." if dry_run else "done.")


if __name__ == "__main__":
    main()
