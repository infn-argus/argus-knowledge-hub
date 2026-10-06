"""A QR code for every asset that has an alias but none: the alias as printed.

An equipment record often carries an alias that is what its label shows, for example the link to its entry in
another system. Scanning that label in the field app finds the record only when a QR label holds the same
value, so for each asset that has an `alias` label and no `qrcode`, this adds one with the alias's value.

Dry run by default: it lists what would change and what is skipped, and changes nothing. With `--apply` it
adds the labels, in one transaction per workspace. A value already printed on another record is skipped and
reported, never moved: the mobile app relies on a scan naming exactly one record.

    python -m app.services.qr_from_alias btf            # plan
    python -m app.services.qr_from_alias btf --apply    # write
"""
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.asset_subresources import AssetLabel

ALIAS_TYPE = "alias"
QR_TYPE = "qrcode"


def plan(db: Session, workspace_id: str) -> dict:
    """What would change in this workspace: the new QR labels, and the aliases that cannot be used."""
    aliases = db.execute(
        select(AssetLabel.asset_uid, AssetLabel.value, Asset.name, Asset.key)
        .join(Asset, Asset.uid == AssetLabel.asset_uid)
        .where(Asset.workspace_id == workspace_id, AssetLabel.type == ALIAS_TYPE, Asset.deleted_at.is_(None))
    ).all()
    has_qr = set(db.scalars(
        select(AssetLabel.asset_uid).join(Asset, Asset.uid == AssetLabel.asset_uid)
        .where(Asset.workspace_id == workspace_id, AssetLabel.type == QR_TYPE)))
    # Values already printed on some record of the workspace: a new QR code must not repeat one.
    taken = {v: uid for uid, v in db.execute(
        select(AssetLabel.asset_uid, AssetLabel.value).join(Asset, Asset.uid == AssetLabel.asset_uid)
        .where(Asset.workspace_id == workspace_id, AssetLabel.type == QR_TYPE)).all()}
    result = {"workspace": workspace_id, "add": [], "skipped": []}
    claimed: dict[str, str] = {}              # value -> asset, for the new labels of this run
    for asset_uid, value, name, key in aliases:
        value = (value or "").strip()
        if not value or asset_uid in has_qr:
            continue
        owner = taken.get(value) or claimed.get(value)
        if owner is not None and owner != asset_uid:
            result["skipped"].append({"asset": key or asset_uid, "name": name, "alias": value,
                                      "reason": f"already the QR code of {owner}"})
            continue
        claimed[value] = asset_uid
        result["add"].append({"asset_uid": asset_uid, "asset": key or asset_uid, "name": name, "value": value})
    return result


def apply(db: Session, workspace_id: str, planned: dict) -> int:
    now = datetime.now(timezone.utc)
    for row in planned["add"]:
        db.add(AssetLabel(uid=str(uuid.uuid4()), asset_uid=row["asset_uid"], type=QR_TYPE, value=row["value"],
                          issuer="argus", verified=False, created_at=now, updated_at=now,
                          metadata_json={"source": "alias", "from_alias": row["value"]}))
    db.commit()
    return len(planned["add"])


def main(argv: list[str]) -> int:
    from app.db import SessionLocal
    from app.models.workspace import Workspace
    if not argv:
        print(__doc__)
        return 2
    target, write = argv[0], "--apply" in argv
    db = SessionLocal()
    try:
        ids = [w.id for w in db.scalars(select(Workspace))] if target == "all" else [target]
        for ws in ids:
            result = plan(db, ws)
            print(f"{ws}: {len(result['add'])} QR code(s) to add, {len(result['skipped'])} skipped")
            for row in result["add"]:
                print(f"  + {row['asset']}  {row['name']}  ←  {row['value']}")
            for row in result["skipped"]:
                print(f"  ! {row['asset']}  {row['name']}  alias {row['alias']}: {row['reason']}")
            if write and result["add"]:
                print(f"  wrote {apply(db, ws, result)} label(s)")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
