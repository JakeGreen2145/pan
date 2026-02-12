"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("discord_id", sa.BigInteger(), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("role", sa.String(20), nullable=False, server_default="tenant"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discord_id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_discord_id", "users", ["discord_id"])
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("rent_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("lease_start", sa.Date(), nullable=False),
        sa.Column("lease_end", sa.Date(), nullable=False),
        sa.Column("late_fee_flat", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("late_fee_daily", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("grace_period_days", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rent_payments",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("date_paid", sa.Date(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rent_payments_tenant_id", "rent_payments", ["tenant_id"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("agent_domain", sa.String(50), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("thread_id", sa.String(100), nullable=True),
        sa.Column("requested_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_agent_domain", "approval_requests", ["agent_domain"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])


def downgrade() -> None:
    op.drop_table("approval_requests")
    op.drop_table("rent_payments")
    op.drop_table("tenants")
    op.drop_table("users")
