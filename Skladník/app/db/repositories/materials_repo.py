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

    async def list_all(self, skip: int = 0, limit: int = 100):
        stmt = select(Material).offset(skip).limit(limit)
        res = await self.session.execute(stmt)
        return res.scalars().all()

    async def create(
        self,
        name: str,
        category: str = None,
        stock: float = 0,
        min_stock: float = 0,
        unit: str = "pcs",
        supplier_id: int = None,
    ):
        material = Material(
            name=name,
            category=category,
            stock=stock,
            min_stock=min_stock,
            unit=unit,
            supplier_id=supplier_id,
        )
        self.session.add(material)
        await self.session.commit()
        await self.session.refresh(material)
        return material
