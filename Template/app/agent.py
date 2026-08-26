from ailacore.db import get_pool


async def process_task(data: dict) -> dict:
    # Vzor: přístup do sdílené Postgres přes jeden pool na proces,
    # ne vlastní DB_CONFIG. Uprav dotaz podle potřeb svého modulu.
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.fetchval("SELECT 1")

    return {"status": "ok", "message": "Zpracováno", "received": data}
