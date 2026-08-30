"""Preserve game version and confidence in knowledge revisions.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("knowledge_revisions")
    }
    added_confidence = "confidence" not in columns
    if "game_version" not in columns:
        op.add_column("knowledge_revisions", sa.Column("game_version", sa.String(length=80)))
    if added_confidence:
        op.add_column(
            "knowledge_revisions",
            sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        )
        op.execute(
            """
            UPDATE knowledge_revisions AS revision
            SET game_version = entry.game_version,
                confidence = entry.confidence
            FROM knowledge_entries AS entry
            WHERE entry.id = revision.entry_id
            """
        )
        op.alter_column("knowledge_revisions", "confidence", nullable=False)


def downgrade() -> None:
    columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("knowledge_revisions")
    }
    if "confidence" in columns:
        op.drop_column("knowledge_revisions", "confidence")
    if "game_version" in columns:
        op.drop_column("knowledge_revisions", "game_version")
