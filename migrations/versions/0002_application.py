"""Add accounts, sessions and report snapshots without altering existing data."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_application"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "app_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_app_sessions_user_id", "app_sessions", ["user_id"])
    op.create_index("ix_app_sessions_expires_at", "app_sessions", ["expires_at"])
    op.create_table(
        "portfolio_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("positions", postgresql.JSONB(), nullable=False),
        sa.Column("analysis", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_portfolio_reports_user_id", "portfolio_reports", ["user_id"])


def downgrade() -> None:
    op.drop_table("portfolio_reports")
    op.drop_table("app_sessions")
    op.drop_table("app_users")
