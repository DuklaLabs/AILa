# app/services/material_service.py
from app.db.repositories.materials_repo import MaterialsRepository


async def list_materials(db, skip: int = 0, limit: int = 100):
    repo = MaterialsRepository(db)
    return await repo.list_all(skip=skip, limit=limit)


async def create_material(
    db,
    name: str,
    category: str = None,
    stock: float = 0,
    min_stock: float = 0,
    unit: str = "pcs",
    supplier_id: int = None,
):
    repo = MaterialsRepository(db)
    return await repo.create(
        name=name,
        category=category,
        stock=stock,
        min_stock=min_stock,
        unit=unit,
        supplier_id=supplier_id,
    )
