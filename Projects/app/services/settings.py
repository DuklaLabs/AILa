"""Konfigurace služby: interní hodinová sazba a týdenní kapacita člověka.

Priorita: řádek v `projects.settings` → env → default. Sazba je pro management
„skryté fixní číslo“ – nikde se needituje přes běžné API (jen migrací nebo
přímým zásahem do `projects.settings`).
"""
import os

from ailacore.db import get_pool

_DEFAULTS = {"hourly_rate_czk": 500.0, "weekly_capacity_hours": 40.0}
_ENV = {
    "hourly_rate_czk": "PROJECTS_HOURLY_RATE_CZK",
    "weekly_capacity_hours": "PROJECTS_WEEKLY_CAPACITY_HOURS",
}


async def get_setting_float(key: str) -> float:
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT value FROM projects.settings WHERE key = $1", key
        )
    if val is not None:
        try:
            return float(val)
        except ValueError:
            pass
    env_val = os.getenv(_ENV.get(key, ""))
    if env_val:
        try:
            return float(env_val)
        except ValueError:
            pass
    return _DEFAULTS.get(key, 0.0)


async def get_hourly_rate() -> float:
    return await get_setting_float("hourly_rate_czk")


async def get_weekly_capacity() -> float:
    return await get_setting_float("weekly_capacity_hours")
