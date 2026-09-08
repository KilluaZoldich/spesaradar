"""Initial durable catalog, jobs, provenance and refresh requests."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "offers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("withdrawn", sa.Boolean(), nullable=False),
        sa.Column("missing_count", sa.Integer(), nullable=False),
        sa.Column("last_missing_at", sa.Float()),
    )
    op.create_index("ix_offers_source_id", "offers", ["source_id"])
    op.create_index("ix_offers_campaign_id", "offers", ["campaign_id"])
    op.create_table(
        "sources",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("last_requested", sa.Float()),
        sa.Column("last_attempt", sa.Float()),
        sa.Column("last_success", sa.Float()),
        sa.Column("next_allowed", sa.Float(), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("completeness", sa.String(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("started_at", sa.Float()),
        sa.Column("finished_at", sa.Float()),
        sa.Column("lease_until", sa.Float()),
        sa.Column("heartbeat_at", sa.Float()),
        sa.Column("lease_token", sa.String()),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("counters", sa.JSON(), nullable=False),
    )
    op.create_index("ix_jobs_source_id", "jobs", ["source_id"])
    op.create_index(
        "one_active_job_per_source",
        "jobs",
        ["source_id"],
        unique=True,
        sqlite_where=sa.text("state IN ('queued','running')"),
    )
    op.create_table(
        "refreshes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("created_at", sa.Float(), nullable=False),
        sa.Column("targets", sa.JSON(), nullable=False),
    )
    op.create_table(
        "captures",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("fetched_at", sa.Float(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("path", sa.Text()),
        sa.Column("etag", sa.Text()),
        sa.Column("modified", sa.Text()),
    )
    op.create_index("ix_captures_source_id", "captures", ["source_id"])


def downgrade():
    for table in ["captures", "refreshes", "jobs", "sources", "offers"]:
        op.drop_table(table)
