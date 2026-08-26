"""add internal.open_hours.hour_number so slots line up with the school's
fixed bell schedule (period 0-10) and can be rendered as a weekly
timetable grid instead of a flat list.

Revision ID: 0006_open_hours_period
Revises: 0005_students_login
Create Date: 2026-08-27

"""
from alembic import op

revision = "0006_open_hours_period"
down_revision = "0005_students_login"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.open_hours
        ADD COLUMN hour_number SMALLINT CHECK (hour_number BETWEEN 0 AND 10);
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE internal.open_hours DROP COLUMN IF EXISTS hour_number;")
