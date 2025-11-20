from fastapi import APIRouter, Depends
from app.db.session import async_session
from app.db.models import Material

router = APIRouter()

@router.get("/")
async def get_all():
    async with async_session() as session:
        res = await session.execute(select(Material))
        return res.scalars().all()
