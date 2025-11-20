import httpx

async def get_low_stock():
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://skladnik:8001/materials/low")
        return resp.json()
