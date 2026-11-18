"""club: flexibilní JSON document store pro Kroužek (ZŠ/SŠ klub).

Kroužek je portovaný samostatný prototyp (statické HTML/JS, localStorage)
pro správu kroužku — žáci, docházka na schůzky, projekty, kontakty, nastavení
po skupinách ZŠ/SŠ. Tvar dat prototypu se mezi sebou liší kolekci od kolekce
a ještě se bude měnit (žádné stabilní FK vztahy, žádné dotazy přes víc
kolekcí) — nevyplatí se to teď plně normalizovat do vlastních tabulek. Místo
toho jedna obecná `club.documents(collection, id, data jsonb)` tabulka, kterou
backend (Krouzek/app/documents.py) vystavuje jako REST API nad libovolnou
kolekcí, a `club.history` jako jednoduchý audit log/undo zdroj (frontend
prototypu měl historii změn s možností vrátit zpět).

Revision ID: 0021_club
Revises: 0020_machines
Create Date: 2026-11-18

"""
from alembic import op

revision = "0021_club"
down_revision = "0020_machines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE SCHEMA IF NOT EXISTS club;

        CREATE TABLE IF NOT EXISTS club.documents (
            collection   TEXT NOT NULL,
            id           TEXT NOT NULL,
            data         JSONB NOT NULL,
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (collection, id)
        );
        CREATE INDEX IF NOT EXISTS ix_club_documents_collection ON club.documents (collection);

        CREATE TABLE IF NOT EXISTS club.history (
            id      SERIAL PRIMARY KEY,
            at      BIGINT NOT NULL,
            path    TEXT,
            op      TEXT,
            before  JSONB,
            label   TEXT,
            undone  BOOLEAN NOT NULL DEFAULT FALSE
        );
        CREATE INDEX IF NOT EXISTS ix_club_history_at ON club.history (at DESC);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS club.history;
        DROP TABLE IF EXISTS club.documents;
        DROP SCHEMA IF EXISTS club;
        """
    )
