"""Perzistence konverzace s Generálem – general.chat_messages, per-uživatel
(auth.users, sdílené SSO přes ailacore.auth). Nahrazuje dřívější
localStorage v prohlížeči: konverzace teď žije v DB, jde k ní přistupovat
z libovolného zařízení po přihlášení."""
import json
from typing import Any, Optional

from ailacore.db import get_pool

HISTORY_LIMIT = 200


async def load_history(user_id: int) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, text, data
            FROM general.chat_messages
            WHERE user_id = $1
            ORDER BY created_at ASC
            LIMIT $2
            """,
            user_id,
            HISTORY_LIMIT,
        )
    return [
        {
            "from": "user" if row["role"] == "user" else "agent",
            "text": row["text"],
            **({"data": json.loads(row["data"])} if row["data"] is not None else {}),
        }
        for row in rows
    ]


async def save_message(user_id: int, role: str, text: str, data: Optional[Any] = None) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO general.chat_messages (user_id, role, text, data)
            VALUES ($1, $2, $3, $4::jsonb)
            """,
            user_id,
            role,
            text,
            json.dumps(data, ensure_ascii=False, default=str) if data is not None else None,
        )
