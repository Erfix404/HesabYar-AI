"""Legal source registry table (ARCHITECTURE.md §1.3 provenance records)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-03

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "legal_sources",
        sa.Column("source_id", sa.String(64), primary_key=True, comment="Stable source identifier"),
        sa.Column(
            "domain",
            sa.String(32),
            nullable=False,
            comment="tax | accounting_standard | moadian_protocol",
        ),
        sa.Column("authority", sa.String(256), nullable=False, comment="Issuing authority"),
        sa.Column("document_number_or_version", sa.String(128), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("published_at", sa.String(32), nullable=True),
        sa.Column("effective_from", sa.String(32), nullable=True),
        sa.Column("effective_to", sa.String(32), nullable=True),
        sa.Column("retrieved_at", sa.String(32), nullable=False),
        sa.Column("canonical_url", sa.Text, nullable=False),
        sa.Column("snapshot_uri", sa.Text, nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column(
            "verification_status",
            sa.String(32),
            nullable=False,
            comment="DRAFT | VERIFIED | CORROBORATED_CURRENT | RETIRED | DISPUTED",
        ),
        sa.Column("verified_by", sa.String(128), nullable=True),
        sa.Column("verified_at", sa.String(32), nullable=True),
        sa.Column("notes", sa.Text, server_default=sa.text("''"), nullable=False),
    )
    op.create_index("ix_legal_sources_domain", "legal_sources", ["domain"])
    op.create_index(
        "ix_legal_sources_verification_status", "legal_sources", ["verification_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_legal_sources_verification_status", table_name="legal_sources")
    op.drop_index("ix_legal_sources_domain", table_name="legal_sources")
    op.drop_table("legal_sources")
