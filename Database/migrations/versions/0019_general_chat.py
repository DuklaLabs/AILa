"""konverzace s Generálem uložené pod účtem uživatele.

Zakládá schéma `general` s tabulkou `chat_messages` – jeden řádek na zprávu
(uživatelovu i Generálovu), vázaný na `auth.users.id`. General/app/main.py
teď vyžaduje přihlášení (dl_session cookie, ailacore.auth.get_current_user)
a při každém POST /general uloží oba konce výměny, ať konverzace přežije
reload i přihlášení z jiného zařízení – dřív žila jen v localStorage
prohlížeče.

Revision ID: 0019_general_chat
Revises: 0018_merge_heads
Create Date: 2026-09-15

"""
from alembic import op

revision = "0019_general_chat"
down_revision = "0018_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS general;")
    op.execute(
        """
        CREATE TABLE general.chat_messages (
            id          BIGSERIAL PRIMARY KEY,
            user_id     INTEGER NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            role        TEXT NOT NULL CHECK (role IN ('user', 'agent')),
            text        TEXT NOT NULL,
            data        JSONB,          -- výsledek CHECK_STOCK/CREATE_ORDER, jen u role='agent'
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX ix_general_chat_messages_user "
        "ON general.chat_messages (user_id, created_at);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS general.chat_messages;")
    op.execute("DROP SCHEMA IF EXISTS general;")
