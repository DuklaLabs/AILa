"""One-off bootstrap: create the first admin user (and optionally an RFID
card for them) once auth.users has no password-based login left to fall
back on. Run after `alembic upgrade head`.

Usage:
    POSTGRES_HOST=localhost python seed_admin.py <username> <password> [card_uid]
"""
import asyncio
import os
import sys

import bcrypt
import asyncpg


async def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    username, password = sys.argv[1], sys.argv[2]
    card_uid = sys.argv[3] if len(sys.argv) > 3 else None

    conn = await asyncpg.connect(
        user=os.getenv("POSTGRES_USER", "agent"),
        password=os.getenv("POSTGRES_PASSWORD", "agentpass"),
        database=os.getenv("POSTGRES_DB", "agentdb"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
    )

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    user_id = await conn.fetchval(
        """
        INSERT INTO auth.users (username, role, password_hash)
        VALUES ($1, 'admin', $2)
        ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash
        RETURNING id
        """,
        username,
        password_hash,
    )
    print(f"admin user '{username}' ready (id={user_id})")

    if card_uid:
        await conn.execute(
            """
            INSERT INTO auth.rfid_cards (user_id, card_uid)
            VALUES ($1, $2)
            ON CONFLICT (card_uid) DO UPDATE SET user_id = EXCLUDED.user_id, is_active = TRUE
            """,
            user_id,
            card_uid,
        )
        print(f"rfid card '{card_uid}' linked to '{username}'")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
