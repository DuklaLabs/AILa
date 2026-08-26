"""add internal.bookings — nothing previously recorded who booked a slot,
so capacity could never actually be enforced.

Revision ID: 0003_bookings
Revises: 0002_web_sessions
Create Date: 2026-08-26

"""
from alembic import op

revision = "0003_bookings"
down_revision = "0002_web_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE internal.bookings (
            id SERIAL PRIMARY KEY,
            student_id INTEGER NOT NULL REFERENCES internal.students(student_id),
            open_hour_id INTEGER NOT NULL REFERENCES internal.open_hours(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            UNIQUE (student_id, open_hour_id)
        );
        """
    )
    op.execute("CREATE INDEX idx_bookings_open_hour_id ON internal.bookings(open_hour_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS internal.bookings;")
