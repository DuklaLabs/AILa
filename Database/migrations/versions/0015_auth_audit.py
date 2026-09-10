"""auth.audit_log – kdo co v RBAC změnil.

Začátek systémového auditního logu (databanka §20). Zatím ho plní jen RBAC
admin API (`ailacore.admin` přes `ailacore.audit.record_audit`), ale tabulka je
schválně obecná, ať se pod ni dají věšet i další moduly.

Revision ID: 0015_auth_audit
Revises: 0014_rbac
Create Date: 2026-09-08

"""
from alembic import op

revision = "0015_auth_audit"
down_revision = "0014_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE auth.audit_log (
            id          BIGSERIAL PRIMARY KEY,
            created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
            actor_id    INTEGER REFERENCES auth.users(id),
            actor_name  VARCHAR(128),          -- snapshot (účet může zaniknout)
            action      VARCHAR(64) NOT NULL,  -- 'role.permissions.set', 'user.roles.set', ...
            target_type VARCHAR(32),           -- 'role' | 'permission' | 'user'
            target_id   VARCHAR(64),           -- jméno role/oprávnění nebo user id
            detail      JSONB,                 -- {added:[...], removed:[...]} nebo {before, after}
            ip          VARCHAR(64)
        );
        """
    )
    op.execute(
        "CREATE INDEX idx_audit_log_created_at ON auth.audit_log (created_at DESC);"
    )
    op.execute(
        "CREATE INDEX idx_audit_log_target ON auth.audit_log (target_type, target_id);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS auth.audit_log;")
