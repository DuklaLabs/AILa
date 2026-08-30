"""one open hour per (date, hour_number) — the admin timetable grid adds
slots per cell, so a duplicate slot for the same day/period is always a
mistake. Postgres allows multiple NULL hour_number rows, so legacy slots
created before 0006 are unaffected.

Revision ID: 0007_open_hours_unique_slot
Revises: 0006_open_hours_period
Create Date: 2026-08-27

"""
from alembic import op

revision = "0007_open_hours_unique_slot"
down_revision = "0006_open_hours_period"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.open_hours
        ADD CONSTRAINT uq_open_hours_date_hour UNIQUE (date, hour_number);
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE internal.open_hours DROP CONSTRAINT IF EXISTS uq_open_hours_date_hour;"
    )
