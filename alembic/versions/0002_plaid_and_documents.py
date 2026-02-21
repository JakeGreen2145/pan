"""plaid and documents

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plaid_items",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column("institution_name", sa.String(200), nullable=False),
        sa.Column("access_token", sa.String(500), nullable=False),
        sa.Column("item_id", sa.String(200), nullable=False),
        sa.Column("cursor", sa.String(500), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id"),
    )

    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "plaid_item_id",
            sa.Uuid(),
            sa.ForeignKey("plaid_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plaid_transaction_id", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("original_description", sa.String(1000), nullable=True),
        sa.Column("payment_channel", sa.String(50), nullable=True),
        sa.Column("is_zelle", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("parsed_sender_name", sa.String(200), nullable=True),
        sa.Column("matched_tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("match_status", sa.String(20), nullable=False, server_default="unmatched"),
        sa.Column("match_confidence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rent_payment_id", sa.Uuid(), sa.ForeignKey("rent_payments.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plaid_transaction_id"),
    )
    op.create_index("ix_bank_transactions_plaid_item_id", "bank_transactions", ["plaid_item_id"])
    op.create_index(
        "ix_bank_transactions_plaid_transaction_id", "bank_transactions", ["plaid_transaction_id"]
    )
    op.create_index(
        "ix_bank_transactions_matched_tenant_id", "bank_transactions", ["matched_tenant_id"]
    )
    op.create_index("ix_bank_transactions_match_status", "bank_transactions", ["match_status"])

    op.create_table(
        "lease_documents",
        sa.Column("id", sa.Uuid(), nullable=False, default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=False),
        sa.Column("lease_start", sa.Date(), nullable=True),
        sa.Column("lease_end", sa.Date(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lease_documents_tenant_id", "lease_documents", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("lease_documents")
    op.drop_table("bank_transactions")
    op.drop_table("plaid_items")
