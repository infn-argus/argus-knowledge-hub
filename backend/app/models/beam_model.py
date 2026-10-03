"""The values of a physics model that depend on its version: kept with the Model Dataset they belong to.

An element's position along a path (`s`), its place in the hall, its strengths, the optics at it and the
simulator's own parameters change with the lattice version, the optics in use and the measurement. They are
not facts about the facility and never properties of the hardware installed there, so they are not ledger
claims on the element: they are one row per (dataset, element, path), replaced when that dataset is imported
again. The dataset itself is a record, with its provenance (source, version, commit, simulator).
"""
from typing import Optional

from sqlalchemy import BigInteger, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


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
