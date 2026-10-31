"""python -m app.catalogue validate [<collection dir> …] [--against <previous catalogue dir>] | list

`validate` checks every collection this installation ships, together; given directories, it checks those
(collections being written) with the shipped ones. `--against` also compares with a previous release (a
checkout of the catalogue at the last tag): nothing may disappear without being retired or transferred, and
content that changed needs a newer version. It exits non-zero when anything is wrong, so CI can run it."""
import sys
from pathlib import Path

from app.catalogue.loader import load, load_tree
from app.catalogue.validate import tree_problems


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    command, rest = argv[0], argv[1:]
    if command == "list":
        for c in load_tree().values():
            needs = ", ".join(f"{k} {v}" for k, v in {**c.requires_packages, **c.requires_collections}.items()) or "—"
            print(f"{c.id} {c.version}  {c.name}  [{c.domain}] {c.summary()}  (owner: {c.owner}; requires: {needs})")
        return 0
    if command == "validate":
        previous = None
        if "--against" in rest:
            i = rest.index("--against")
            if i + 1 >= len(rest):
                print("--against needs a directory")
                return 2
            previous = load_tree(rest[i + 1])
            rest = rest[:i] + rest[i + 2:]
        tree = load_tree()
        named = [load(Path(d)) for d in rest]
        tree.update({c.id: c for c in named})
        report = tree_problems(tree, previous)
        shown = [c.id for c in named] if named else list(tree)
        bad = 0
        for cid in shown:
            c, problems = tree[cid], report.get(cid, [])
            if problems:
                bad += 1
                print(f"✗ {cid} {c.version}: {len(problems)} problem(s)")
                for p in problems:
                    print(f"    {p.file}" + (f" › {p.where}" if p.where else "") + f": {p.message}")
            else:
                print(f"✓ {cid} {c.version} ({c.summary()}) sha256:{c.checksum[:12]}")
        for cid in sorted(set(report) - set(tree)):          # gone since the previous release
            bad += 1
            for p in report[cid]:
                print(f"✗ {cid}: {p.message}")
        return 1 if bad else 0
    print(f"unknown command {command!r}\n{__doc__}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
