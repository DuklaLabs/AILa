"""link internal.students to auth.users so students can log in with a
password (registration now creates both a roster row and an account,
reusing the same auth.users/password_hash/web_sessions machinery already
built for staff/admin — not a second parallel auth system).

Revision ID: 0005_students_login
Revises: 0004_students_class_group
Create Date: 2026-08-27

"""
from alembic import op

revision = "0005_students_login"
down_revision = "0004_students_class_group"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.students
        ADD COLUMN user_id INTEGER UNIQUE REFERENCES auth.users(id);
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE internal.students DROP COLUMN IF EXISTS user_id;")
