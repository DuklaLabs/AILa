from app.db.models import Material
from sqlalchemy import select

class MaterialsRepository:
    def __init__(self, session):
        self.session = session

    async def get_all(self):
        res = await self.session.execute(select(Material))
        return res.scalars().all()

    async def get_below_min_stock(self):
        stmt = select(Material).where(Material.stock < Material.min_stock)
        res = await self.session.execute(stmt)
        return res.scalars().all()
