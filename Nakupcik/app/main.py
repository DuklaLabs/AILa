from fastapi import FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from app.session import async_session, engine
from app.models import Base, Material, MaterialMovement

from pydantic import BaseModel
from typing import Optional, List


app = FastAPI(title="Inventory Agent (Skladník)")


# ---------- Pydantic schémata ----------

class MaterialCreate(BaseModel):
    name: str
    category: Optional[str] = None
    stock: float = 0
    min_stock: float = 0
    unit: str = "pcs"


class MaterialUpdateStock(BaseModel):
    quantity: float
    note: Optional[str] = None


class MaterialOut(BaseModel):
    id: int
    name: str
    category: Optional[str]
    stock: float
    min_stock: float
    unit: str

    class Config:
        from_attributes = True


# ---------- Startup: vytvoření tabulek ----------

@app.on_event("startup")
async def on_startup():
    # vytvoří tabulky v SQLite, pokud ještě nejsou
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------- Endpointy pro materiály ----------

@app.post("/materials", response_model=MaterialOut)
async def create_material(data: MaterialCreate):
    async with async_session() as session:
        material = Material(
            name=data.name,
            category=data.category,
            stock=data.stock,
            min_stock=data.min_stock,
            unit=data.unit,
        )
        session.add(material)
        await session.commit()
        await session.refresh(material)

        # pokud zakládáš materiál se startovní zásobou != 0, uděláme pohyb
        if data.stock != 0:
            movement = MaterialMovement(
                material_id=material.id,
                change=data.stock,
                note="Initial stock",
            )
            session.add(movement)
            await session.commit()

        return material


@app.get("/materials", response_model=List[MaterialOut])
async def list_materials():
    async with async_session() as session:
        res = await session.execute(select(Material))
        materials = res.scalars().all()
        return materials


@app.get("/materials/{material_id}", response_model=MaterialOut)
async def get_material(material_id: int):
    async with async_session() as session:
        material = await session.get(Material, material_id)
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        return material


@app.post("/materials/{material_id}/add", response_model=MaterialOut)
async def add_stock(material_id: int, data: MaterialUpdateStock):
    """Příjem na sklad: zvýšení zásoby"""
    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    async with async_session() as session:
        material = await session.get(Material, material_id)
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        material.stock += data.quantity
        session.add(material)

        movement = MaterialMovement(
            material_id=material.id,
            change=data.quantity,
            note=data.note or "Stock increase",
        )
        session.add(movement)

        await session.commit()
        await session.refresh(material)
        return material


@app.post("/materials/{material_id}/remove", response_model=MaterialOut)
async def remove_stock(material_id: int, data: MaterialUpdateStock):
    """Výdej ze skladu: snížení zásoby"""
    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    async with async_session() as session:
        material = await session.get(Material, material_id)
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")

        new_stock = material.stock - data.quantity
        if new_stock < 0:
            raise HTTPException(status_code=400, detail="Not enough stock")

        material.stock = new_stock
        session.add(material)

        movement = MaterialMovement(
            material_id=material.id,
            change=-data.quantity,
            note=data.note or "Stock decrease",
        )
        session.add(movement)

        await session.commit()
        await session.refresh(material)
        return material


@app.get("/materials/low", response_model=List[MaterialOut])
async def list_low_stock():
    """
    Vrátí materiály, kde stock < min_stock.
    Na tohle se pak může ptát Nákupčí a Generál.
    """
    async with async_session() as session:
        stmt = select(Material).where(Material.stock < Material.min_stock)
        res = await session.execute(stmt)
        materials = res.scalars().all()
        return materials


@app.get("/health")
async def health():
    return {"status": "ok", "service": "inventory_agent"}
