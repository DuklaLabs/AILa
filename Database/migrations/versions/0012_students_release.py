"""souhlas s uvolňováním studenta z výuky pro DuklaLabs.

Při registraci se zeptáme třídního učitele i koordinátora. Dokud oba
neodsouhlasí, student se NEsmí zapsat na otevřenou hodinu, která mu podle
rozvrhu jeho třídy koliduje s vlastní výukou (na volné hodiny se zapsat může).

  release_teacher_ok   – souhlas třídního učitele  (NULL/ TRUE / FALSE)
  release_coord_ok      – souhlas koordinátora     (NULL/ TRUE / FALSE)
  release_token         – neuhodnutelný token do schvalovacího odkazu
  release_class_teacher – jméno třídního učitele zjištěné při registraci
                          (snapshot pro zobrazení; prázdné = nezjištěn)

Revision ID: 0012_students_release
Revises: 0011_bookings_attendance
Create Date: 2026-09-07

"""
from alembic import op

revision = "0012_students_release"
down_revision = "0011_bookings_attendance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.students
            ADD COLUMN release_teacher_ok BOOLEAN,
            ADD COLUMN release_coord_ok BOOLEAN,
            ADD COLUMN release_token VARCHAR(64) UNIQUE,
            ADD COLUMN release_class_teacher TEXT;
        """
    )
    op.execute(
        """
        UPDATE internal.students
        SET release_token = md5(random()::text || clock_timestamp()::text || student_id::text)
        WHERE release_token IS NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.students
            DROP COLUMN IF EXISTS release_teacher_ok,
            DROP COLUMN IF EXISTS release_coord_ok,
            DROP COLUMN IF EXISTS release_token,
            DROP COLUMN IF EXISTS release_class_teacher;
        """
    )
