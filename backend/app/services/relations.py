from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, Relation


def rebuild_asset_relations(db: Session, asset_uid: str) -> None:
    """Recompute Asset.outbound_relations/inbound_relations from the Relation
    table. These are a denormalized cache (consumed by e.g. the mobile sync
    API) that can drift from the source of truth whenever a relation changes
    or a global-visibility flag changes what an asset can legitimately point
    at — this is the one place that resyncs them."""
    asset = db.get(Asset, asset_uid)
    if asset is None:
        return
    outbound = list(
        db.scalars(select(Relation.to_asset_uid).where(Relation.from_asset_uid == asset_uid))
    )
    inbound = list(
        db.scalars(select(Relation.from_asset_uid).where(Relation.to_asset_uid == asset_uid))
    )
    # Assign only on change: this runs on every read of an object, and an
    # unconditional write bumps updated_at, so merely looking at an object
    # made it "recently changed" everywhere activity is shown.
    if list(asset.outbound_relations or []) != outbound:
        asset.outbound_relations = outbound
    if list(asset.inbound_relations or []) != inbound:
        asset.inbound_relations = inbound


def rebuild_asset_relations_with_neighbors(db: Session, asset_uid: str) -> None:
    """Rebuild the asset's own cache plus every asset it's directly related
    to — used when the asset's own global-visibility flag changes, since a
    neighbor's cached list may reference this asset."""
    rebuild_asset_relations(db, asset_uid)
    neighbor_uids = set(
        db.scalars(select(Relation.to_asset_uid).where(Relation.from_asset_uid == asset_uid))
    ) | set(
        db.scalars(select(Relation.from_asset_uid).where(Relation.to_asset_uid == asset_uid))
    )
    for neighbor_uid in neighbor_uids:
        rebuild_asset_relations(db, neighbor_uid)


def rebuild_relations_for_schemas(db: Session, schema_uids: list[str]) -> None:
    """Rebuild relation caches for every asset belonging to any of the given
    schemas — used when a type's global flag changes (which can cascade to
    descendant types), affecting cross-workspace visibility for every
    instance of those types."""
    if not schema_uids:
        return
    asset_uids = db.scalars(select(Asset.uid).where(Asset.schema_uid.in_(schema_uids))).all()
    for asset_uid in asset_uids:
        rebuild_asset_relations_with_neighbors(db, asset_uid)
