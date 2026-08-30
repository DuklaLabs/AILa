"""add internal.open_hours.supervisor — when staff plan a free hour in the
admin grid they pick which supervising teacher covers it (chosen from the
DUKLA_SUPERVISORS list). Plain text, nullable; not an FK because the names
come from the separate duklamaps timetable, not auth.users.

Revision ID: 0008_open_hours_supervisor
Revises: 0007_open_hours_unique_slot
Create Date: 2026-08-27

"""
from alembic import op

revision = "0008_open_hours_supervisor"
down_revision = "0007_open_hours_unique_slot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE internal.open_hours ADD COLUMN supervisor VARCHAR(128);")


def downgrade() -> None:
    op.execute("ALTER TABLE internal.open_hours DROP COLUMN IF EXISTS supervisor;")
