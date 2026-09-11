"""Index individual community loadout messages and avoid repeated media analysis."""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    constraints = {c["name"] for c in inspector.get_unique_constraints("community_loadouts")}
    if "uq_community_loadouts_guild_thread" in constraints:
        op.drop_constraint(
            "uq_community_loadouts_guild_thread", "community_loadouts", type_="unique"
        )
    columns = {c["name"] for c in inspector.get_columns("community_loadouts")}
    if "source_fingerprint" not in columns:
        op.add_column(
            "community_loadouts", sa.Column("source_fingerprint", sa.String(64), nullable=True)
        )


def downgrade() -> None:
    raise RuntimeError(
        "Restore the pre-upgrade backup to downgrade without losing member loadouts."
    )
