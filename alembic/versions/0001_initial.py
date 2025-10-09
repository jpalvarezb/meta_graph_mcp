"""Initial schema for tokens, webhooks, jobs, and calendar notes."""

from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON

revision = "0001_initial"
down_revision = None
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "tokens",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("type", sa.Enum("page", "instagram", "ad_account", "system_user", name="token_type"), nullable=False),
        sa.Column("subject_id", sa.String(length=255), nullable=False),
        sa.Column("scopes", JSON, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("app_id", sa.String(length=64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("raw_metadata", JSON, nullable=False, server_default=sa.text("'{}'")),
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("topic", sa.String(length=128), nullable=False, index=True),
        sa.Column("object_id", sa.String(length=255), nullable=False, index=True),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload", JSON, nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "succeeded", "failed", name="job_status"), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
    )

    op.create_check_constraint("ck_jobs_attempts_nonnegative", "jobs", "attempts >= 0")

    op.create_table(
        "calendar_notes",
        sa.Column("idempotency_key", sa.String(length=128), primary_key=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("when", sa.DateTime(timezone=True), nullable=False),
        sa.Column("related_ids", JSON, nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_table("calendar_notes")
    op.drop_constraint("ck_jobs_attempts_nonnegative", "jobs", type_="check")
    op.drop_table("jobs")
    op.drop_table("webhook_events")
    op.drop_table("tokens")
    op.execute("DROP TYPE IF EXISTS token_type")
    op.execute("DROP TYPE IF EXISTS job_status")
