"""Add moderated community claim learning.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "community_claims" not in tables:
        op.create_table(
            "community_claims",
            sa.Column("guild_id", sa.BigInteger(), nullable=False),
            sa.Column("source_channel_id", sa.BigInteger(), nullable=False),
            sa.Column("source_message_id", sa.BigInteger(), nullable=False),
            sa.Column("submitter_user_id", sa.BigInteger()),
            sa.Column("member_label", sa.String(length=80), nullable=False),
            sa.Column("source_question", sa.Text(), nullable=False),
            sa.Column("prior_answer_excerpt", sa.Text(), nullable=False),
            sa.Column("claim_text", sa.Text(), nullable=False),
            sa.Column("search_text", sa.Text(), nullable=False),
            sa.Column("source_url", sa.Text(), nullable=False),
            sa.Column("game_version", sa.String(length=80), nullable=False),
            sa.Column("risk_flag", sa.String(length=40)),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("review_message_id", sa.BigInteger()),
            sa.Column("reviewed_by_user_id", sa.BigInteger()),
            sa.Column("review_note", sa.Text()),
            sa.Column("reviewed_at", sa.DateTime(timezone=True)),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_community_claims"),
            sa.UniqueConstraint(
                "guild_id",
                "source_message_id",
                name="uq_community_claims_guild_source_message",
            ),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_community_claims_search_text_trgm "
        "ON community_claims USING gin (search_text gin_trgm_ops)"
    )
    for column in (
        "guild_id",
        "submitter_user_id",
        "game_version",
        "status",
        "review_message_id",
    ):
        op.execute(
            f"CREATE INDEX IF NOT EXISTS ix_community_claims_{column} "
            f"ON community_claims ({column})"
        )


def downgrade() -> None:
    if "community_claims" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("community_claims")
