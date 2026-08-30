#!/bin/sh
# Runs once on every `docker compose up`, before the app services start:
# brings the shared Postgres schema to head, then (only if ADMIN_USERNAME
# and ADMIN_PASSWORD are set) makes sure a password admin account exists.
# Idempotent - safe to re-run against an already-migrated database.
set -e

echo "[db-migrate] alembic upgrade head"
alembic upgrade head

if [ -n "$ADMIN_USERNAME" ] && [ -n "$ADMIN_PASSWORD" ]; then
  echo "[db-migrate] ensuring admin user '$ADMIN_USERNAME'"
  # ADMIN_CARD_UID intentionally unquoted: empty -> no third arg.
  python seed_admin.py "$ADMIN_USERNAME" "$ADMIN_PASSWORD" $ADMIN_CARD_UID
fi

echo "[db-migrate] done"
