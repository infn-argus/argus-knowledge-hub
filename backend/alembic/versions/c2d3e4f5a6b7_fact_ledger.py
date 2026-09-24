"""The fact ledger: claims, events, decisions and their projections.

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

J = postgresql.JSONB(astext_type=sa.Text())
TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.add_column("assets", sa.Column("record_status", sa.String(), nullable=False, server_default="Active"))
    op.add_column("assets", sa.Column("merged_into_uid", sa.String(), nullable=True))
    op.add_column("relations", sa.Column("derivation", sa.String(), nullable=True))
    op.add_column("relations", sa.Column("rule", sa.String(), nullable=True))

    op.create_table(
        "ledger_streams",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("facility", sa.String(), nullable=True),
        sa.Column("may_create", J, nullable=False, server_default="[]"),
        sa.Column("frozen_at", TS, nullable=True),
        sa.Column("created_at", TS, nullable=True),
    )
    op.create_table(
        "ledger_source_revisions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("stream_id", sa.String(), sa.ForeignKey("ledger_streams.id", ondelete="CASCADE"), index=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False, index=True),
        sa.Column("parser_version", sa.String(), nullable=False),
        sa.Column("observed_at", TS, nullable=False),
        sa.Column("retrieved_at", TS, nullable=True),
        sa.Column("parent_revision_id", sa.String(), nullable=True),
        sa.Column("ordering", sa.String(), nullable=False, server_default="head"),
        sa.Column("parse_skipped", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "ledger_claims",
        sa.Column("claim_id", sa.String(), primary_key=True),
        sa.Column("stream_id", sa.String(), nullable=False, index=True),
        sa.Column("source_ref", sa.String(), nullable=False, index=True),
        sa.Column("predicate", sa.String(), nullable=False),
        sa.Column("member", sa.String(), nullable=True),
        sa.Column("polarity", sa.String(), nullable=False, server_default="present"),
        sa.Column("value", J, nullable=True),
        sa.Column("method", sa.String(), nullable=False),
        sa.Column("rule_id", sa.String(), nullable=True),
        sa.Column("derived_from", J, nullable=False, server_default="[]"),
    )
    op.create_table(
        "ledger_claim_events",
        sa.Column("seq", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("claim_id", sa.String(), nullable=False, index=True),
        sa.Column("stream_id", sa.String(), nullable=False, index=True),
        sa.Column("revision_id", sa.String(), nullable=False, index=True),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("impl_version", sa.String(), nullable=True),
        sa.Column("evidence", J, nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("at", TS, nullable=True),
    )
    op.create_table(
        "ledger_revision_events",
        sa.Column("seq", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("revision_id", sa.String(), nullable=False, index=True),
        sa.Column("stream_id", sa.String(), nullable=False, index=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("cause", sa.String(), nullable=True),
        sa.Column("detail", J, nullable=True),
        sa.Column("at", TS, nullable=True),
    )
    op.create_table(
        "ledger_decisions",
        sa.Column("seq", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("batch_id", sa.String(), nullable=False, index=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("subject_uid", sa.String(), nullable=True, index=True),
        sa.Column("predicate", sa.String(), nullable=True),
        sa.Column("member", sa.String(), nullable=True),
        sa.Column("value", J, nullable=True),
        sa.Column("target", J, nullable=True),
        sa.Column("supersedes", J, nullable=False, server_default="[]"),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("effective_at", TS, nullable=True),
        sa.Column("at", TS, nullable=True),
    )
    op.create_table(
        "ledger_status_events",
        sa.Column("seq", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("subject_uid", sa.String(), nullable=False, index=True),
        sa.Column("predicate", sa.String(), nullable=False),
        sa.Column("member", sa.String(), nullable=True),
        sa.Column("contributor", sa.String(), nullable=False),
        sa.Column("from_status", sa.String(), nullable=True),
        sa.Column("to_status", sa.String(), nullable=False),
        sa.Column("cause", sa.String(), nullable=False),
        sa.Column("projector_version", sa.String(), nullable=False),
        sa.Column("at", TS, nullable=True),
    )
    for name, extra in (
        ("ledger_identity_events", [sa.Column("source_ref", sa.String(), nullable=False, index=True),
                                    sa.Column("uid", sa.String(), nullable=False),
                                    sa.Column("kind", sa.String(), nullable=False),
                                    sa.Column("cause", sa.String(), nullable=False)]),
        ("ledger_record_events", [sa.Column("uid", sa.String(), nullable=False, index=True),
                                  sa.Column("kind", sa.String(), nullable=False),
                                  sa.Column("before", J, nullable=True),
                                  sa.Column("after", J, nullable=True),
                                  sa.Column("cause", sa.String(), nullable=False)]),
        ("ledger_conflict_events", [sa.Column("conflict_id", sa.String(), nullable=False, index=True),
                                    sa.Column("kind", sa.String(), nullable=False),
                                    sa.Column("conflict_type", sa.String(), nullable=False),
                                    sa.Column("subject_uid", sa.String(), nullable=False, index=True),
                                    sa.Column("predicate", sa.String(), nullable=True),
                                    sa.Column("member", sa.String(), nullable=True),
                                    sa.Column("detail", J, nullable=True),
                                    sa.Column("cause", sa.String(), nullable=False)]),
    ):
        op.create_table(name, sa.Column("seq", sa.BigInteger(), primary_key=True, autoincrement=True),
                        *extra, sa.Column("at", TS, nullable=True))
    op.create_table(
        "ledger_policies",
        sa.Column("version", sa.String(), primary_key=True),
        sa.Column("body", J, nullable=False),
        sa.Column("vocabulary", J, nullable=False),
        sa.Column("report", J, nullable=False, server_default="{}"),
        sa.Column("activated_by", sa.String(), nullable=False),
        sa.Column("activated_at", TS, nullable=True),
    )
    op.create_table(
        "ledger_job_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("stage", sa.String(), nullable=False, index=True),
        sa.Column("stage_version", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False, index=True),
        sa.Column("input_digest", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("counts", J, nullable=False, server_default="{}"),
        sa.Column("at", TS, nullable=True),
    )
    op.create_table(
        "ledger_stream_heads",
        sa.Column("stream_id", sa.String(), primary_key=True),
        sa.Column("parsed_head", sa.String(), nullable=True),
        sa.Column("parsed_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_head", sa.String(), nullable=True),
        sa.Column("published_number", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "ledger_identity_bindings",
        sa.Column("source_ref", sa.String(), primary_key=True),
        sa.Column("uid", sa.String(), nullable=False, index=True),
    )
    op.create_table(
        "ledger_fact_state",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("subject_uid", sa.String(), nullable=False, index=True),
        sa.Column("predicate", sa.String(), nullable=False),
        sa.Column("member", sa.String(), nullable=True),
        sa.Column("contributor", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("rank", sa.String(), nullable=True),
        sa.Column("effective", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "ledger_conflicts",
        sa.Column("conflict_id", sa.String(), primary_key=True),
        sa.Column("conflict_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False, index=True),
        sa.Column("subject_uid", sa.String(), nullable=False, index=True),
        sa.Column("predicate", sa.String(), nullable=True),
        sa.Column("member", sa.String(), nullable=True),
        sa.Column("detail", J, nullable=False, server_default="{}"),
        sa.Column("opened_seq", sa.BigInteger(), nullable=False),
    )
    # Audit tables are append-only. The application role should hold only
    # INSERT and SELECT on them; that grant is deployment configuration
    # (see docs/asset-model-revision.md §3.3), not something a migration run
    # as the owner can enforce on itself.


def downgrade() -> None:
    for name in ("ledger_conflicts", "ledger_fact_state", "ledger_identity_bindings", "ledger_stream_heads",
                 "ledger_job_runs", "ledger_policies", "ledger_conflict_events", "ledger_record_events",
                 "ledger_identity_events", "ledger_status_events", "ledger_decisions",
                 "ledger_revision_events", "ledger_claim_events", "ledger_claims",
                 "ledger_source_revisions", "ledger_streams"):
        op.drop_table(name)
    op.drop_column("relations", "rule")
    op.drop_column("relations", "derivation")
    op.drop_column("assets", "merged_into_uid")
    op.drop_column("assets", "record_status")
