"""Add full knowledge search text and the community loadout corpus.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    knowledge_columns = {column["name"] for column in inspector.get_columns("knowledge_entries")}
    if "search_text" not in knowledge_columns:
        op.add_column("knowledge_entries", sa.Column("search_text", sa.Text(), nullable=True))
        op.execute(
            """
            UPDATE knowledge_entries
            SET search_text = lower(
                concat_ws(
                    ' ', subject, entity_type, claim_key,
                    content::text, context::text, coalesce(game_version, '')
                )
            )
            """
        )
        op.alter_column("knowledge_entries", "search_text", nullable=False)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_search_text_trgm
        ON knowledge_entries USING gin (search_text gin_trgm_ops)
        """
    )

    if "community_loadouts" not in tables:
        op.create_table(
            "community_loadouts",
            sa.Column("guild_id", sa.BigInteger(), nullable=False),
            sa.Column("forum_channel_id", sa.BigInteger(), nullable=False),
            sa.Column("thread_id", sa.BigInteger(), nullable=False),
            sa.Column("starter_message_id", sa.BigInteger(), nullable=False),
            sa.Column("author_user_id", sa.BigInteger(), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("search_text", sa.Text(), nullable=False),
            sa.Column("source_url", sa.Text(), nullable=False),
            sa.Column("game_version", sa.String(length=80), nullable=False),
            sa.Column(
                "verification_status",
                sa.String(length=40),
                nullable=False,
            ),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_community_loadouts"),
            sa.UniqueConstraint(
                "guild_id",
                "starter_message_id",
                name="uq_community_loadouts_guild_starter_message",
            ),
            sa.UniqueConstraint(
                "guild_id",
                "thread_id",
                name="uq_community_loadouts_guild_thread",
            ),
        )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_community_loadouts_search_text_trgm
        ON community_loadouts USING gin (search_text gin_trgm_ops)
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_community_loadouts_author_user_id "
        "ON community_loadouts (author_user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_community_loadouts_forum_channel_id "
        "ON community_loadouts (forum_channel_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_community_loadouts_game_version "
        "ON community_loadouts (game_version)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_community_loadouts_guild_id ON community_loadouts (guild_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_community_loadouts_active ON community_loadouts (active)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_community_loadouts_verification_status "
        "ON community_loadouts (verification_status)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "community_loadouts" in set(inspector.get_table_names()):
        op.drop_table("community_loadouts")
    knowledge_columns = {column["name"] for column in inspector.get_columns("knowledge_entries")}
    if "search_text" in knowledge_columns:
        op.execute("DROP INDEX IF EXISTS ix_knowledge_search_text_trgm")
        op.drop_column("knowledge_entries", "search_text")
