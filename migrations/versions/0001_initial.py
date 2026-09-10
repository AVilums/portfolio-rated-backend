"""initial schema

Revision ID: 0001_initial
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    jsonb = postgresql.JSONB()
    op.create_table(
        "portfolios",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "positions",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("portfolio_id", uuid, sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("instrument", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False),
        sa.UniqueConstraint("portfolio_id", "instrument"),
    )
    op.create_table(
        "market_prices",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("instrument", sa.String(50), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.UniqueConstraint("instrument", "as_of"),
    )
    op.create_table(
        "risk_calculations",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("portfolio_id", uuid, sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("value", sa.Numeric(20, 8), nullable=False),
        sa.Column("inputs", jsonb, nullable=False),
        sa.Column(
            "calculated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", uuid),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    for table in ("audit_events", "risk_calculations", "market_prices", "positions", "portfolios"):
        op.drop_table(table)
