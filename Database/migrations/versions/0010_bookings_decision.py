"""add supervisor-decision fields to internal.bookings — the notification
e-mail sent to a free hour's dozor now carries Povolit / Zamítnout buttons,
and the click has to land somewhere.

  decision_token  – unguessable per-booking token used in the e-mail link
                    (the teacher has no account; the token is the capability)
  approved        – NULL = nerozhodnuto, TRUE = uvolnění povoleno,
                    FALSE = účast zamítnuta
  decided_at      – kdy dozor naposledy rozhodl (rozhodnutí je přepsatelné)

Revision ID: 0010_bookings_decision
Revises: 0009_open_hours_supervisor_multi
Create Date: 2026-09-07

"""
from alembic import op

revision = "0010_bookings_decision"
down_revision = "0009_open_hours_supervisor_multi"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.bookings
            ADD COLUMN decision_token VARCHAR(64) UNIQUE,
            ADD COLUMN approved BOOLEAN,
            ADD COLUMN decided_at TIMESTAMP;
        """
    )
    # Backfill tokens for pre-existing bookings so a re-sent link would work
    # (no pgcrypto dependency — md5 of random text is enough here).
    op.execute(
        """
        UPDATE internal.bookings
        SET decision_token = md5(random()::text || clock_timestamp()::text || id::text)
        WHERE decision_token IS NULL;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE internal.bookings
            DROP COLUMN IF EXISTS decision_token,
            DROP COLUMN IF EXISTS approved,
            DROP COLUMN IF EXISTS decided_at;
        """
    )
