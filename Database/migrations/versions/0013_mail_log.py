"""log odeslaných e-mailů – aby bylo 100% dohledatelné, že (a kdy) mail odešel.

Zapisuje služba Messenger při každém pokusu o odeslání (i chybu / dry-run).
Neukládá tělo e-mailu (jen předmět, příjemce, stav) – pokud je potřeba i tělo,
Messenger má přepínač MAIL_LOG_BODY.

Revision ID: 0013_mail_log
Revises: 0012_students_release
Create Date: 2026-09-08

"""
from alembic import op

revision = "0013_mail_log"
down_revision = "0012_students_release"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS messaging;")
    op.execute(
        """
        CREATE TABLE messaging.mail_log (
            id              BIGSERIAL PRIMARY KEY,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            backend         TEXT,                       -- graph | smtp
            to_addrs        TEXT[] NOT NULL DEFAULT '{}',
            cc_addrs        TEXT[] NOT NULL DEFAULT '{}',
            bcc_addrs       TEXT[] NOT NULL DEFAULT '{}',
            subject         TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL,              -- OK | ERROR | DRY_RUN | DISABLED
            error           TEXT,
            delivered_to    TEXT,                       -- skutečná adresa při MAIL_REDIRECT_TO (jinak NULL = jako to_addrs)
            redirected_from TEXT,                       -- původní příjemci při MAIL_REDIRECT_TO (pro čtení)
            has_ics         BOOLEAN NOT NULL DEFAULT FALSE,
            body_bytes      INTEGER,
            body            TEXT,                       -- jen když MAIL_LOG_BODY=true
            source          TEXT                        -- volitelný štítek volajícího
        );
        """
    )
    op.execute("CREATE INDEX idx_mail_log_created_at ON messaging.mail_log (created_at DESC);")
    op.execute("CREATE INDEX idx_mail_log_status ON messaging.mail_log (status);")
    op.execute("CREATE INDEX idx_mail_log_to ON messaging.mail_log USING GIN (to_addrs);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS messaging.mail_log;")
    op.execute("DROP SCHEMA IF EXISTS messaging;")
