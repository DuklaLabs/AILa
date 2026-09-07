"""add attendance fields to internal.bookings — dozor DuklaLabs si na
rozhodovací stránce odklikává, zda student na otevřenou hodinu skutečně
přišel (podklad pro omluvení zameškané výuky).

  attended     – NULL = nezkontrolováno, TRUE = přišel, FALSE = nepřišel
  attended_at  – kdy dozor naposledy zaznamenal docházku

Revision ID: 0011_bookings_attendance
Revises: 0010_bookings_decision
Create Date: 2026-09-07

"""
from alembic import op

revision = "0011_bookings_attendance"
down_revision = "0010_bookings_decision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.bookings
            ADD COLUMN attended BOOLEAN,
            ADD COLUMN attended_at TIMESTAMP;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.bookings
            DROP COLUMN IF EXISTS attended,
            DROP COLUMN IF EXISTS attended_at;
        """
    )
