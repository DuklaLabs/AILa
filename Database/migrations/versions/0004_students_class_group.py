"""add internal.students.class_group — the registration form
(student_register.html) already collects it, but the column never
existed, so every registration failed with a DB error.

Revision ID: 0004_students_class_group
Revises: 0003_bookings
Create Date: 2026-08-26

"""
from alembic import op

revision = "0004_students_class_group"
down_revision = "0003_bookings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE internal.students ADD COLUMN class_group VARCHAR(16);")


def downgrade() -> None:
    op.execute("ALTER TABLE internal.students DROP COLUMN IF EXISTS class_group;")
