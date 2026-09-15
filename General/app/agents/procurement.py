import os

import httpx

PROCUREMENT_URL = os.getenv("PROCUREMENT_URL", "http://nakupcik:8002")


async def create_order_from_low_stock():
    """Calls the not-yet-implemented Nakupcik endpoint for turning low-stock
    materials into an order. Nakupcik itself doesn't run yet (see its
    README), so this currently fails with a connection error — that's
    expected until Nakupcik exists."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{PROCUREMENT_URL}/orders/from-low-stock")
        resp.raise_for_status()
        return resp.json()
