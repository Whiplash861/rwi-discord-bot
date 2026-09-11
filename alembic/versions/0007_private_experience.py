"""Private peer endorsements and independently reviewed experience labels."""

from alembic import op
from rwi_bot.db.models import MemberEndorsement, MemberExperience, MemberObservation

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    MemberEndorsement.__table__.create(op.get_bind(), checkfirst=True)
    MemberExperience.__table__.create(op.get_bind(), checkfirst=True)
    MemberObservation.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    raise RuntimeError("Restore a pre-upgrade backup; private endorsements must not be discarded.")
