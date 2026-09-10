"""Zápis do systémového auditního logu (`auth.audit_log`, migrace 0015).

Sdílené – ať to používá RBAC admin API i budoucí moduly. `record_audit` bere
existující connection, aby zápis auditu byl ve stejné transakci jako sama změna
(buď se zapíše obojí, nebo nic).
"""
import json
from typing import Optional

import asyncpg

from .models import User


async def record_audit(
    conn: asyncpg.Connection,
    *,
    actor: Optional[User],
    action: str,
    target_type: str,
    target_id: str,
    detail: dict,
    ip: Optional[str] = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO auth.audit_log
            (actor_id, actor_name, action, target_type, target_id, detail, ip)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
        """,
        actor.id if actor else None,
        (actor.full_name or actor.username) if actor else None,
        action,
        target_type,
        str(target_id),
        json.dumps(detail, ensure_ascii=False, default=str),
        ip,
    )
