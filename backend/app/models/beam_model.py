"""The values of a physics model that depend on its version: kept with the Model Dataset they belong to.

An element's position along a path (`s`), its place in the hall, its strengths, the optics at it and the
simulator's own parameters change with the lattice version, the optics in use and the measurement. They are
not facts about the facility and never properties of the hardware installed there, so they are not ledger
claims on the element: they are one row per (dataset, element, path), replaced when that dataset is imported
again. The dataset itself is a record, with its provenance (source, version, commit, simulator).
"""
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import utcnow


class BeamModelValue(Base):
    __tablename__ = "beam_model_values"
    __table_args__ = (UniqueConstraint("dataset_uid", "subject_uid", "path_uid", name="uq_beam_model_value"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    dataset_uid: Mapped[str] = mapped_column(String, ForeignKey("assets.uid", ondelete="CASCADE"), index=True)
    # The element (or path) the values are of, and the path the coordinate is along.
    subject_uid: Mapped[str] = mapped_column(String, ForeignKey("assets.uid", ondelete="CASCADE"), index=True)
    path_uid: Mapped[Optional[str]] = mapped_column(String, ForeignKey("assets.uid", ondelete="CASCADE"),
                                                    nullable=True, index=True)
    s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    z: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yaw: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pitch: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    roll: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Normalised physics parameters (length, k1, angle…), optics (beta_x, alpha_x, dx, mux…) and the
    # simulator's own type and parameters, kept whole so nothing is lost in translation.
    physics: Mapped[dict] = mapped_column(JSONB, default=dict)
    optics: Mapped[dict] = mapped_column(JSONB, default=dict)
    native: Mapped[dict] = mapped_column(JSONB, default=dict)


class BeamModelDocument(Base):
    """A canonical model as imported (argus.beam-model/2, v1 upgraded): one row per revision, the newest
    `current`. The ledger holds what the hub reasons on (records, topology, observables); the document keeps
    the rest whole — definitions, boundaries, materials, states, measurement models, supports, fields along
    paths — so an export gives back what came in and the model's own queries (limiting aperture, alignment)
    run on it."""
    __tablename__ = "beam_model_documents"
    __table_args__ = (UniqueConstraint("workspace_id", "model_id", "revision", name="uq_beam_model_document"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[str] = mapped_column(String, index=True)
    revision: Mapped[str] = mapped_column(String)                 # sha256 of the canonical JSON, 12 chars
    current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    document: Mapped[dict] = mapped_column(JSONB)
    report: Mapped[dict] = mapped_column(JSONB, default=dict)    # validation: levels, warnings, gaps
    imported_by: Mapped[str] = mapped_column(String)
    imported_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class BeamAssetBinding(Base):
    """A model component's binding to a physical asset, with how it came about (docs/beam-asset-sync.md).

    Status: proposed, ambiguous, confirmed, rejected (unmatched is the absence of a row). Authority says how
    much it can be trusted: authoritative (an authoritative source), human_confirmed, auto_accepted (by the
    configured policy, from a high-confidence proposal), suggestion. A confirmed `implemented_by` binding is
    also an Installation, so the asset's history, power, controls and documents follow the position."""
    __tablename__ = "beam_asset_bindings"
    __table_args__ = (UniqueConstraint("workspace_id", "model_id", "component_id", "relation", "asset_uid",
                                       name="uq_beam_asset_binding"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    model_id: Mapped[str] = mapped_column(String, index=True)
    component_id: Mapped[str] = mapped_column(String, index=True)
    component_uid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    relation: Mapped[str] = mapped_column(String, default="implemented_by")
    asset_uid: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, index=True)
    authority: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    candidates: Mapped[list] = mapped_column(JSONB, default=list)
    method: Mapped[str] = mapped_column(String, default="asset_sync")
    matcher: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    matcher_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)  # the asset as it was when bound: name, s
    installation_uid: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decided_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decided_at: Mapped[Optional[object]] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
