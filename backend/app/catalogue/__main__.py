"""python -m app.catalogue validate [<collection dir> …] [--against <previous catalogue dir>] | list
                   | export --workspace <id> --out <dir> | sources | status

`validate` checks every collection this installation ships, together; given directories, it checks those
(collections being written) with the shipped ones. `--against` also compares with a previous release (a
checkout of the catalogue at the last tag): nothing may disappear without being retired or transferred, and
content that changed needs a newer version. It exits non-zero when anything is wrong, so CI can run it.

`export` reads a workspace's Vendors and Product Models (it writes nothing in ARGUS) and writes candidate
collections, this installation's migration manifest and a report to <dir> (app/catalogue/export.py).

`status` says which workspace is the installation's catalogue, what it holds, which workspaces hang from it,
how many units in each point at its models, and its collections (app/catalogue/system.py). Read-only."""
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
    if command == "status":
        from app.catalogue.system import status
        from app.db import SessionLocal
        db = SessionLocal()
        try:
            s = status(db)
        finally:
            db.rollback()
            db.close()
        if s["designated"] is None:
            print("no catalogue workspace designated")
            print(f"workspaces holding the global Asset type: {', '.join(s['candidates']) or 'none'}")
            return 1
        print(f"catalogue: {s['designated']} ({s['name']})")
        print("records: " + ", ".join(f"{n} {t}" for t, n in sorted(s["records"].items())))
        print(f"not shared (is_global false): {s['not_shared']}")
        print(f"other records: {', '.join(f'{n} {t}' for t, n in s['other_records'].items()) or 'none'}")
        print(f"types: {s['shared_types']} shared, {s['own_types']} its own")
        others = [c for c in s["candidates"] if c != s["designated"]]
        if others:
            print(f"other workspaces holding a global Asset type: {', '.join(others)}")
        print("hanging from it: " + ("; ".join(f"{w} ({', '.join(p)})" for w, p in s["hanging"].items()) or "none"))
        print(f"units pointing at its models: {sum(s['units'].values())} — "
              + (", ".join(f"{w} {n}" for w, n in s["units"].items()) or "none"))
        print("collections: " + (", ".join(f"{c} {v}" for c, v in s["collections"].items()) or "none installed"))
        return 0
    if command == "sources":
        from app.catalogue.sources import describe, lock_path, materialize
        pins = describe()
        if not pins:
            print(f"no lock file ({lock_path()}): the collections are the folders there")
            return 0
        for p in pins:
            print(f"{p['id']}: {p['kind']} {p['repo']} @ {p['ref'] or ''} {p['commit']}")
        print(f"read into {materialize()}")
        return 0
    if command == "export":
        args = dict(zip(rest[::2], rest[1::2]))
        if "--workspace" not in args or "--out" not in args:
            print("export needs --workspace <id> --out <dir>")
            return 2
        from app.catalogue.export import export
        from app.db import SessionLocal
        db = SessionLocal()
        try:
            result = export(db, args["--workspace"], Path(args["--out"]))
        finally:
            db.close()
        print(f"{result['rows']} records: {result['becomes']}; candidates for {', '.join(result['collections'])}; "
              f"{result['problems']} validator problem(s). Read {result['out']}/report.md")
        return 0
    print(f"unknown command {command!r}\n{__doc__}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
