"""Users, server sessions and ownership; preserve unowned legacy requests."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    if op.get_bind().dialect.name == "sqlite":
        # Native ADD COLUMN avoids rebuilding a table referenced by suggestions,
        # feedback and its own parent FK. NULL default preserves legacy records.
        op.execute(
            "ALTER TABLE generation_requests ADD COLUMN user_id VARCHAR(36) REFERENCES users(id)"
        )
    else:
        op.add_column("generation_requests", sa.Column("user_id", sa.String(36), nullable=True))
        op.create_foreign_key(
            "fk_generation_requests_user_id", "generation_requests", "users", ["user_id"], ["id"]
        )
    op.create_index("ix_generation_requests_user_id", "generation_requests", ["user_id"])


def downgrade():
    op.drop_index("ix_generation_requests_user_id", table_name="generation_requests")
    if op.get_bind().dialect.name == "sqlite":
        # SQLite >= 3.35 (supported Python 3.12 environments).
        op.execute("ALTER TABLE generation_requests DROP COLUMN user_id")
    else:
        op.drop_constraint(
            "fk_generation_requests_user_id", "generation_requests", type_="foreignkey"
        )
        op.drop_column("generation_requests", "user_id")
    op.drop_table("auth_sessions")
    op.drop_table("users")
