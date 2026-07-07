"""remove email candidate confidence

Revision ID: 0010_remove_email_candidate_confidence
Revises: 0009_meeting_handoff
Create Date: 2026-07-08
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_remove_email_candidate_confidence"
down_revision = "0009_meeting_handoff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("email_candidates", "confidence")


def downgrade() -> None:
    op.add_column(
        "email_candidates",
        sa.Column("confidence", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("email_candidates", "confidence", server_default=None)
