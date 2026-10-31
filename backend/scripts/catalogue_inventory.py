"""Admin script: a read-only inventory of the Product Models and Vendors there are, before the catalogue
collections' format is frozen (docs/catalogue-collections.md §0).

It opens a read-only transaction and writes nothing. For every workspace, or those named, it reports the
models and vendors (global and local), how vendors are written, what models lack, duplicates within and across
workspaces, which kinds of units use each model (cross-domain use), every reference that points at a model,
the attribute keys in use beyond the type's own, and a small sample.

Usage (in the API pod, or anywhere with the backend's virtualenv and DATABASE_URL set):
  python scripts/catalogue_inventory.py [--workspace ID ...] [--out DIR] [--sample N]

It writes DIR/catalogue-inventory.json and DIR/catalogue-inventory.md (default DIR: the current directory).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

# The backend directory: this script's parent when run from scripts/, else the current directory (a copy run
# from /tmp in the API pod, with `cd /app`). Never "/": there `app` would be the /app work directory itself.
_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _here if os.path.isfile(os.path.join(_here, "app", "db.py")) else os.getcwd())

from sqlalchemy import select, text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models.asset import Asset, Relation  # noqa: E402
from app.models.asset_subresources import AssetLabel  # noqa: E402
from app.models.document import DocumentRelation  # noqa: E402
from app.models.schema import Schema  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402
from app.services.catalogue_mapping import norm, norm_model  # noqa: E402

MODEL, VENDOR = "Product Model", "Vendor"
MODEL_OWN = {"vendor", "vendor_ref", "model_code", "device_class", "datasheet_url", "firmware_version", "eol_date",
             "mtbf_hours", "typical_spares", "inventory_url", "description", "argus_keywords"}


def lineage_names(schemas: list[Schema], root: str) -> set[str]:
    """The names of the types that are `root` or descend from it, in any workspace."""
    by_uid = {s.uid: s for s in schemas}
    out = set()
    for s in schemas:
        seen, cur = set(), s
        while cur is not None and cur.uid not in seen:
            if cur.name == root:
                out.add(s.name)
                break
            seen.add(cur.uid)
            cur = by_uid.get(cur.parent_schema_uid) if cur.parent_schema_uid else None
    return out


def values(v) -> list:
    return v if isinstance(v, list) else [v]


def inventory(db, workspaces: list[str] | None, sample: int) -> dict:
    schemas = list(db.scalars(select(Schema).where(Schema.applies_to == "objects")))
    model_types, vendor_types = lineage_names(schemas, MODEL), lineage_names(schemas, VENDOR)
    # Every attribute, on any type, that refers to a model or a vendor: what would break if a uid changed.
    model_refs, vendor_refs = set(), set()
    for s in schemas:
        for a in s.attributes or []:
            if a.get("type") == "reference":
                # Stored as the type's name (`referenceType`) and uid; packages write `reference`.
                target = a.get("referenceType") or a.get("reference")
                if target in model_types:
                    model_refs.add(a["key"])
                elif target in vendor_types:
                    vendor_refs.add(a["key"])
    names = {w.id: w.name for w in db.scalars(select(Workspace))}

    q = select(Asset).where(Asset.deleted_at.is_(None))
    models, vendors, units = {}, {}, []
    for a in db.scalars(q.execution_options(yield_per=2000)):
        if a.type in model_types:
            models[a.uid] = a
        elif a.type in vendor_types:
            vendors[a.uid] = a
        elif any(k in (a.attributes or {}) for k in model_refs):
            units.append((a.uid, a.workspace_id, a.type, {k: (a.attributes or {}).get(k) for k in model_refs}))
    in_scope = (lambda ws: ws in workspaces) if workspaces else (lambda ws: True)

    # Who points at each model.
    used_by: dict[str, Counter] = defaultdict(Counter)            # model uid -> (workspace, type, key) counts
    for _uid, ws, typ, refs in units:
        for key, v in refs.items():
            for target in values(v):
                if target in models:
                    used_by[target][(ws, typ, key)] += 1
    rel_counts = Counter()
    for frm, to in db.execute(select(Relation.from_asset_uid, Relation.to_asset_uid)):
        if to in models:
            rel_counts[to] += 1
        if frm in models:
            rel_counts[frm] += 1
    label_counts = Counter(u for (u,) in db.execute(select(AssetLabel.asset_uid)) if u in models or u in vendors)
    doc_counts = Counter(u for (u,) in db.execute(select(DocumentRelation.to_uid)) if u in models or u in vendors)

    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "workspaces_named": workspaces or "all",
              "model_types": sorted(model_types), "vendor_types": sorted(vendor_types),
              "model_reference_keys": sorted(model_refs), "vendor_reference_keys": sorted(vendor_refs),
              "per_workspace": {}, "duplicates": [], "vendor_spellings": [], "cross_domain": [],
              "extra_attribute_keys": {}, "dangling": {"vendor_ref": [], "unit_product_model": 0}, "samples": {}}

    per_ws: dict[str, Counter] = defaultdict(Counter)
    for v in vendors.values():
        if in_scope(v.workspace_id):
            per_ws[v.workspace_id]["vendors_global" if v.is_global else "vendors_local"] += 1
    spellings: dict[str, Counter] = defaultdict(Counter)
    groups: dict[tuple, list] = defaultdict(list)
    extra = Counter()
    for m in models.values():
        if not in_scope(m.workspace_id):
            continue
        at = m.attributes or {}
        c = per_ws[m.workspace_id]
        c["models_global" if m.is_global else "models_local"] += 1
        c["with_units"] += 1 if used_by.get(m.uid) else 0
        for missing in ("model_code", "device_class"):
            c[f"no_{missing}"] += 0 if at.get(missing) else 1
        vendor_name = at.get("vendor")
        ref = at.get("vendor_ref")
        if ref and ref in vendors:
            vendor_name = vendors[ref].name
        elif ref:
            report["dangling"]["vendor_ref"].append({"model": m.uid, "vendor_ref": ref})
        if not vendor_name:
            c["no_vendor"] += 1
        elif not ref:
            c["vendor_text_only"] += 1
        if vendor_name:
            spellings[norm(vendor_name)][vendor_name] += 1
        groups[(norm(vendor_name), norm_model(at.get("model_code") or m.name))].append(m)
        extra.update(k for k in at if k not in MODEL_OWN)
    for v in vendors.values():
        if in_scope(v.workspace_id):
            spellings[norm(v.name)][v.name] += 1

    for ws, c in sorted(per_ws.items()):
        report["per_workspace"][ws] = {"name": names.get(ws, ws), **dict(sorted(c.items()))}
    for (vn, mc), ms in groups.items():
        if len(ms) > 1 and mc:
            report["duplicates"].append({
                "vendor": vn, "model": mc, "workspaces": sorted({m.workspace_id for m in ms}),
                "records": [{"uid": m.uid, "key": m.key, "name": m.name, "workspace": m.workspace_id,
                             "units": sum(used_by.get(m.uid, Counter()).values())} for m in ms]})
    report["vendor_spellings"] = [{"normalised": k, "spellings": dict(v)} for k, v in sorted(spellings.items())
                                  if len(v) > 1]
    for uid, uses in used_by.items():
        m = models[uid]
        if not in_scope(m.workspace_id):
            continue
        types = sorted({t for (_ws, t, _k) in uses})
        wss = sorted({w for (w, _t, _k) in uses})
        if len(types) > 1 or len(wss) > 1:
            report["cross_domain"].append({"uid": uid, "key": m.key, "name": m.name, "unit_types": types,
                                           "workspaces": wss})
    report["dangling"]["unit_product_model"] = sum(
        1 for _uid, _ws, _t, refs in units for v in refs.values() for t in values(v)
        if t and isinstance(t, str) and t not in models and len(t) > 8)
    report["extra_attribute_keys"] = dict(extra.most_common())

    refs_total = Counter()
    for uid, uses in used_by.items():
        for (_ws, _t, key), n in uses.items():
            refs_total[key] += n
    report["references"] = {"unit_attributes": dict(refs_total), "relations": sum(rel_counts.values()),
                            "labels": sum(label_counts.values()), "document_links": sum(doc_counts.values())}

    by_ws: dict[str, list] = defaultdict(list)
    for m in models.values():
        if in_scope(m.workspace_id):
            by_ws[m.workspace_id].append(m)
    for ws, ms in by_ws.items():
        ms.sort(key=lambda m: -sum(used_by.get(m.uid, Counter()).values()))
        report["samples"][ws] = [{"uid": m.uid, "key": m.key, "name": m.name, "type": m.type,
                                  "global": m.is_global, "attributes": m.attributes,
                                  "units": sum(used_by.get(m.uid, Counter()).values()),
                                  "relations": rel_counts[m.uid], "labels": label_counts[m.uid],
                                  "document_links": doc_counts[m.uid]} for m in ms[:sample]]
    return report


def markdown(r: dict) -> str:
    out = ["# Catalogue inventory", "", f"Generated {r['generated_at']}, workspaces: {r['workspaces_named']}.",
           "Read-only: nothing was written.", "",
           f"Model types: {', '.join(r['model_types']) or '—'}. Vendor types: {', '.join(r['vendor_types']) or '—'}.",
           f"Attributes that refer to a model: {', '.join(r['model_reference_keys']) or '—'}.", "",
           "## Per workspace", "",
           "| Workspace | Models (global / local) | Vendors (global / local) | Used by units | No model code | "
           "No device class | No vendor | Vendor as text only |", "|---|---|---|---|---|---|---|---|"]
    for ws, c in r["per_workspace"].items():
        out.append(f"| {c['name']} (`{ws}`) | {c.get('models_global', 0)} / {c.get('models_local', 0)} | "
                   f"{c.get('vendors_global', 0)} / {c.get('vendors_local', 0)} | {c.get('with_units', 0)} | "
                   f"{c.get('no_model_code', 0)} | {c.get('no_device_class', 0)} | {c.get('no_vendor', 0)} | "
                   f"{c.get('vendor_text_only', 0)} |")
    refs = r["references"]
    out += ["", "## References to models", "",
            f"Unit attributes: {refs['unit_attributes'] or '—'}; relations: {refs['relations']}; "
            f"labels: {refs['labels']}; document links: {refs['document_links']}.",
            f"Dangling: {len(r['dangling']['vendor_ref'])} vendor references to a missing vendor, "
            f"{r['dangling']['unit_product_model']} unit references to a missing model.", "",
            f"## Duplicates ({len(r['duplicates'])})", ""]
    for d in r["duplicates"][:200]:
        recs = "; ".join(f"{x['name']} (`{x['key']}`, {x['workspace']}, {x['units']} units)" for x in d["records"])
        out.append(f"- **{d['vendor'] or '(no vendor)'} / {d['model']}**: {recs}")
    out += ["", f"## Vendor spellings that normalise to one name ({len(r['vendor_spellings'])})", ""]
    out += [f"- `{v['normalised']}`: " + ", ".join(f"{k} ({n})" for k, n in v["spellings"].items())
            for v in r["vendor_spellings"][:200]]
    out += ["", f"## Models used across unit types or workspaces ({len(r['cross_domain'])})", ""]
    out += [f"- {c['name']} (`{c['key']}`): {', '.join(c['unit_types'])} — in {', '.join(c['workspaces'])}"
            for c in r["cross_domain"][:200]]
    out += ["", "## Attribute keys on models beyond the type's own", ""]
    out += [f"- `{k}`: {n}" for k, n in list(r["extra_attribute_keys"].items())[:60]] or ["- none"]
    out += ["", "## Decisions this informs", "",
            "1. Collection boundaries: the domains the models' units belong to, and the cross-domain models.",
            "2. Vendor aliases: the spellings above become `aliases` of one vendor entry.",
            "3. Required fields: whether `model_code` and `device_class` can be required, given how many lack them.",
            "4. `specifications`: which of the extra attribute keys become typed specification keys.",
            "5. Adoption effort: duplicates to merge, and the references each merge must keep.", ""]
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--workspace", action="append", help="limit to this workspace (repeatable); default: all")
    p.add_argument("--out", default=".", help="directory for catalogue-inventory.json and .md")
    p.add_argument("--sample", type=int, default=20, help="sample models per workspace (default 20)")
    args = p.parse_args()
    db = SessionLocal()
    try:
        db.execute(text("SET TRANSACTION READ ONLY"))
        report = inventory(db, args.workspace, args.sample)
    finally:
        db.rollback()
        db.close()
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "catalogue-inventory.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)
    with open(os.path.join(args.out, "catalogue-inventory.md"), "w") as f:
        f.write(markdown(report))
    print(f"wrote {args.out}/catalogue-inventory.json and .md: {len(report['per_workspace'])} workspaces, "
          f"{len(report['duplicates'])} duplicate groups, {len(report['cross_domain'])} cross-domain models")


if __name__ == "__main__":
    main()
