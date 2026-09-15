import os

import httpx

INVENTORY_URL = os.getenv("INVENTORY_URL", "http://skladnik:8001")


async def get_low_stock():
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{INVENTORY_URL}/materials/low")
        resp.raise_for_status()
        return resp.json()
