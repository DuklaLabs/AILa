"""dedupe internal.lesson_hours / internal.excused so the new DuklaMaps
timetable lookup (app/timetable_client.py) can upsert idempotently on
ON CONFLICT instead of inserting duplicate rows on every booking.

Revision ID: 0008_lesson_hours_dedup
Revises: 0016_projects
Create Date: 2026-08-26

"""
from alembic import op

revision = "0008_lesson_hours_dedup"
down_revision = "0016_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.lesson_hours
        ADD CONSTRAINT uq_lesson_hours_slot UNIQUE (date, class_name, hour_number);

        ALTER TABLE internal.excused
        ADD CONSTRAINT uq_excused_student_lesson UNIQUE (student_id, lesson_id);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.excused DROP CONSTRAINT IF EXISTS uq_excused_student_lesson;
        ALTER TABLE internal.lesson_hours DROP CONSTRAINT IF EXISTS uq_lesson_hours_slot;
        """
    )
