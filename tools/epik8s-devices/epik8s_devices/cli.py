"""epik8s-devices — turn a beamline's control configuration into an inventory.

Three steps, kept separate on purpose. `scan` reads the configuration and
writes a file you can open and correct. `match` proposes which physical
asset each device already is. `push` writes the result into a hub.

Nothing is written anywhere until you run `push`, and `push` names the
workspace it is about to write into before it does.
"""
import argparse
import csv
import json
import sys
from dataclasses import asdict
from typing import Optional

import yaml

from .catalogue import load_templates
from .hub import Hub, HubError
from .match import Inventory
from .scan import Device, scan_file

DEFAULT_TEMPLATES = "../infn-epics-ioc/ibek-templates"


def _write(rows: list[dict], path: Optional[str], fmt: str) -> None:
    if fmt == "csv":
        columns = ["key", "beamline", "ioc", "name", "pv", "device_class", "vendor",
                   "model", "element", "system", "physical_asset", "needs"]
        handle = open(path, "w", newline="") if path else sys.stdout
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "needs": "; ".join(row.get("needs") or [])})
        if path:
            handle.close()
        return

    text = (json.dumps(rows, indent=2, default=str) if fmt == "json"
            else yaml.safe_dump(rows, sort_keys=False, allow_unicode=True))
    if path:
        with open(path, "w") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)


def _summary(rows: list[dict]) -> str:
    total = len(rows)
    classified = sum(1 for r in rows if r.get("device_class"))
    elements = sum(1 for r in rows if r.get("element"))
    specs = sum(1 for r in rows if r.get("model_spec"))
    by_class: dict[str, int] = {}
    for row in rows:
        by_class[row.get("device_class") or "(unclassified)"] = \
            by_class.get(row.get("device_class") or "(unclassified)", 0) + 1
    lines = [
        f"{total} devices — {classified} classified from an ibek template, "
        f"{elements} with the element they serve read from the name, "
        f"{specs} carrying a rating (ps:/motor:)",
    ]
    for name, count in sorted(by_class.items(), key=lambda kv: -kv[1]):
        lines.append(f"    {count:5d}  {name}")
    return "\n".join(lines)


def cmd_scan(args) -> int:
    templates = load_templates(args.templates)
    if not templates:
        print(f"! no ibek templates found at {args.templates} — devices will be "
              f"classified only where a built-in fallback covers them",
              file=sys.stderr)
    else:
        print(f"{len(templates)} device templates read from {args.templates}",
              file=sys.stderr)

    devices: list[Device] = []
    for path in args.values:
        found = scan_file(path, templates)
        print(f"{path}: {len(found)} devices", file=sys.stderr)
        devices.extend(found)

    rows = [asdict(d) for d in devices]
    print(_summary(rows), file=sys.stderr)
    _write(rows, args.out, args.format)
    if args.out:
        print(f"\nwritten to {args.out} — open it, correct it, then `match` or `push`",
              file=sys.stderr)
    return 0


def cmd_match(args) -> int:
    rows = yaml.safe_load(open(args.devices)) or []
    hub = Hub(args.hub, args.token)
    me = hub.whoami()
    workspace = me.get("workspace_id") or (me.get("user") or {}).get("email") or "?"
    print(f"matching against {args.hub} as workspace {workspace}", file=sys.stderr)

    inventory = Inventory(hub.assets())
    print(f"{len(inventory.assets)} objects in the inventory", file=sys.stderr)

    matched = ambiguous = 0
    for row in rows:
        proposal = inventory.for_device(row)
        if proposal.get("uid"):
            row["physical_asset"] = proposal["uid"]
            row["physical_asset_evidence"] = {
                k: v for k, v in proposal.items() if k != "uid"
            }
            matched += 1
        elif proposal.get("ambiguous"):
            row["physical_asset_candidates"] = proposal["ambiguous"]
            ambiguous += 1

    print(f"{matched} proposed, {ambiguous} with more than one candidate "
          f"(left for you), {len(rows) - matched - ambiguous} unmatched",
          file=sys.stderr)
    _write(rows, args.out or args.devices, "yaml")
    return 0


def cmd_push(args) -> int:
    rows = yaml.safe_load(open(args.devices)) or []
    hub = Hub(args.hub, args.token)
    me = hub.whoami()
    workspace = me.get("workspace_id") or "(the token's workspace)"

    classes = sorted({r.get("device_class") or "Unclassified Device" for r in rows})
    print(f"About to write {len(rows)} objects into workspace {workspace} "
          f"at {args.hub}")
    print(f"  types used: {', '.join(classes)}")
    if args.dry_run:
        print("  --dry-run: nothing written")
        return 0
    if not args.yes:
        answer = input("Type the workspace id to confirm: ").strip()
        if answer != workspace:
            print("Not confirmed; nothing written.")
            return 1

    existing = {s["name"]: s for s in hub.schemas()}
    for name in classes:
        if name not in existing:
            created = hub.create_schema(
                uid=f"epik8s-{name.lower().replace(' ', '-')}",
                name=name,
                description=f"{name} driven by the control system.",
            )
            existing[name] = created
            print(f"  created type {name}")

    written = failed = 0
    for row in rows:
        type_name = row.get("device_class") or "Unclassified Device"
        payload = {
            "uid": f"epik8s-{row['key'].lower().replace(':', '-')}",
            "schema_uid": existing[type_name]["uid"],
            "key": row["key"],
            "name": row["name"],
            "type": type_name,
            "attributes": {
                k: v for k, v in row.items()
                if k not in ("key", "name", "device_class") and v not in (None, [], {})
            },
        }
        try:
            if hub.get_asset(payload["uid"]):
                hub.update_asset(payload["uid"], {"attributes": payload["attributes"]})
            else:
                hub.create_asset(payload)
            written += 1
        except HubError as e:
            failed += 1
            print(f"  ! {row['key']}: {e}", file=sys.stderr)
    print(f"{written} written, {failed} failed")
    return 0 if not failed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="epik8s-devices",
        description="Turn an EPIK8s beamline configuration into a device inventory.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan_parser = sub.add_parser("scan", help="read values.yaml into a device list")
    scan_parser.add_argument("values", nargs="+", help="one or more values.yaml")
    scan_parser.add_argument("--templates", default=DEFAULT_TEMPLATES,
                             help="path to infn-epics-ioc/ibek-templates")
    scan_parser.add_argument("--out", help="write here instead of stdout")
    scan_parser.add_argument("--format", choices=("yaml", "json", "csv"), default="yaml")
    scan_parser.set_defaults(func=cmd_scan)

    match_parser = sub.add_parser("match", help="propose the physical asset each device is")
    match_parser.add_argument("devices", help="the file `scan` wrote")
    match_parser.add_argument("--hub", required=True, help="https://assets-api…")
    match_parser.add_argument("--token", required=True, help="a workspace PAT")
    match_parser.add_argument("--out", help="write here instead of in place")
    match_parser.set_defaults(func=cmd_match)

    push_parser = sub.add_parser("push", help="write the devices into a hub workspace")
    push_parser.add_argument("devices", help="the file `scan`/`match` wrote")
    push_parser.add_argument("--hub", required=True)
    push_parser.add_argument("--token", required=True)
    push_parser.add_argument("--dry-run", action="store_true")
    push_parser.add_argument("--yes", action="store_true",
                             help="skip the workspace confirmation")
    push_parser.set_defaults(func=cmd_push)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except HubError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
