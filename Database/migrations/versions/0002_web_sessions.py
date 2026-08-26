"""rename auth.sessions to attendance_log, add web_sessions + password_hash

auth.sessions was actually an entry/exit attendance log, not an HTTP
session table — renaming it now avoids a name collision with the real
session mechanism introduced here for RFID/password SSO.

Revision ID: 0002_web_sessions
Revises: 0001_baseline
Create Date: 2026-08-26

"""
from alembic import op

revision = "0002_web_sessions"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE auth.sessions RENAME TO attendance_log;")
    op.execute("ALTER TABLE auth.users ADD COLUMN password_hash VARCHAR(256);")
    op.execute(
        """
        CREATE TABLE auth.web_sessions (
            token VARCHAR(128) PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES auth.users(id),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP
        );
        """
    )
    op.execute("CREATE INDEX idx_web_sessions_user_id ON auth.web_sessions(user_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS auth.web_sessions;")
    op.execute("ALTER TABLE auth.users DROP COLUMN IF EXISTS password_hash;")
    op.execute("ALTER TABLE auth.attendance_log RENAME TO sessions;")
