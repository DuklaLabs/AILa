"""Single shared asyncpg pool for every AILa service.

Every service used to open its own `DB_CONFIG` dict and call
`asyncpg.create_pool(...)` per request (see the old AccessRequest
`students.py`/`open_hours.py`). That both duplicated connection settings
across services and leaked a brand-new pool on every request. This module
is the one place that owns the pool per process — call `get_pool()` from
request handlers, and wire `close_pool()` into your app's shutdown event.
"""
import os
from typing import Optional

import asyncpg

_pool: Optional[asyncpg.Pool] = None


def _connection_kwargs() -> dict:
    return {
        "user": os.getenv("POSTGRES_USER", "agent"),
        "password": os.getenv("POSTGRES_PASSWORD", "agentpass"),
        "database": os.getenv("POSTGRES_DB", "agentdb"),
        "host": os.getenv("POSTGRES_HOST", "postgres"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
    }


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(**_connection_kwargs())
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
