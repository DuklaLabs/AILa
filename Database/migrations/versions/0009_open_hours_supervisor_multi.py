"""widen internal.open_hours.supervisor to TEXT — a free hour can now be
assigned to one *or more* supervising teachers, stored as a comma-separated
list ("Petrášek Jan, Hlaváč Václav"). VARCHAR(128) was too tight for that.

Revision ID: 0009_open_hours_supervisor_multi
Revises: 0008_open_hours_supervisor
Create Date: 2026-08-27

"""
from alembic import op

revision = "0009_open_hours_supervisor_multi"
down_revision = "0008_open_hours_supervisor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE internal.open_hours ALTER COLUMN supervisor TYPE TEXT;")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE internal.open_hours "
        "ALTER COLUMN supervisor TYPE VARCHAR(128) USING LEFT(supervisor, 128);"
    )
