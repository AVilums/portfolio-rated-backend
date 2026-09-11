"""Store versioned ETF data without modifying existing reports or legacy market tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_etf_data"
down_revision = "0002_application"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "etf_data_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticker", sa.String(40), nullable=False),
        sa.Column("exchange", sa.String(40), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.clock_timestamp(),
        ),
        sa.UniqueConstraint(
            "source", "ticker", "exchange", "as_of", "digest", name="uq_etf_snapshot_content"
        ),
    )
    op.create_index(
        "ix_etf_snapshot_lookup", "etf_data_snapshots", ["ticker", "exchange", "source", "as_of"]
    )


def downgrade() -> None:
    op.drop_table("etf_data_snapshots")
