"""Add durable Raid and Incursion operation scheduling.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "scheduled_operations" not in tables:
        op.create_table(
            "scheduled_operations",
            sa.Column("guild_id", sa.BigInteger(), nullable=False),
            sa.Column("organizer_user_id", sa.BigInteger(), nullable=False),
            sa.Column("activity", sa.String(length=120), nullable=False),
            sa.Column("activity_type", sa.String(length=30), nullable=False),
            sa.Column("organizer_role", sa.String(length=40), nullable=False),
            sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("capacity", sa.Integer(), nullable=False),
            sa.Column("notes", sa.Text()),
            sa.Column("source_channel_id", sa.BigInteger()),
            sa.Column("announcement_channel_id", sa.BigInteger()),
            sa.Column("announcement_message_id", sa.BigInteger()),
            sa.Column("reminder_message_id", sa.BigInteger()),
            sa.Column("matchmaking_role_id", sa.BigInteger()),
            sa.Column("reminder_sent_at", sa.DateTime(timezone=True)),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_scheduled_operations"),
            sa.UniqueConstraint(
                "announcement_message_id",
                name="uq_scheduled_operations_announcement_message_id",
            ),
            sa.UniqueConstraint(
                "reminder_message_id",
                name="uq_scheduled_operations_reminder_message_id",
            ),
        )
        for column in (
            "guild_id",
            "organizer_user_id",
            "activity",
            "activity_type",
            "start_at",
            "status",
        ):
            op.create_index(
                f"ix_scheduled_operations_{column}",
                "scheduled_operations",
                [column],
            )
    if "operation_rsvps" not in tables:
        op.create_table(
            "operation_rsvps",
            sa.Column("operation_id", sa.Uuid(), nullable=False),
            sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("selected_role", sa.String(length=40), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["operation_id"],
                ["scheduled_operations.id"],
                name="fk_operation_rsvps_operation_id_scheduled_operations",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint(
                "operation_id",
                "discord_user_id",
                name="pk_operation_rsvps",
            ),
        )
        op.create_index("ix_operation_rsvps_status", "operation_rsvps", ["status"])


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "operation_rsvps" in tables:
        op.drop_table("operation_rsvps")
    if "scheduled_operations" in tables:
        op.drop_table("scheduled_operations")
