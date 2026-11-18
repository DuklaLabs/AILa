from app.db.models import Supplier
from sqlalchemy import select


async def list_suppliers(db, skip: int = 0, limit: int = 100):
    stmt = select(Supplier).offset(skip).limit(limit)
    res = await db.execute(stmt)
    return res.scalars().all()


async def create_supplier(db, name: str, contact: str = None):
    supplier = Supplier(name=name, contact=contact)
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier


async def get_supplier(db, supplier_id: int):
    stmt = select(Supplier).where(Supplier.id == supplier_id)
    res = await db.execute(stmt)
    return res.scalars().first()
