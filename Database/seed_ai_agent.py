"""One-off bootstrap: create the service account AI scripts (Pocket task
translator, ...) log in as when calling AILa services. Role 'member' already
carries `projects.ai:use`, which is all `propose_change` needs — proposals
still land as `pending` and require a human with `projects.proposal:review`
to approve them, so this account can never write anything by itself.

Usage:
    POSTGRES_HOST=localhost python seed_ai_agent.py <username> <password>
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
        INSERT INTO auth.users (username, full_name, role, password_hash)
        VALUES ($1, 'AI Agent (Pocket translator)', 'member', $2)
        ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash
        RETURNING id
        """,
        username,
        password_hash,
    )
    print(f"ai-agent user '{username}' ready (id={user_id}, role=member)")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
