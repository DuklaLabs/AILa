from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.session import async_session
from app.db.models import Base, Material, Order, OrderItem
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session() as session:
        async with session.begin():
            await session.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Procurement Agent – Minimal Version", lifespan=lifespan)


@app.post("/materials")
async def add_material(name: str, stock: float = 0, min_stock: float = 0):
    async with async_session() as session:
        material = Material(name=name, stock=stock, min_stock=min_stock)
        session.add(material)
        await session.commit()
        await session.refresh(material)
        return material


@app.get("/materials")
async def list_materials():
    async with async_session() as session:
        res = await session.execute(select(Material))
        return res.scalars().all()


@app.get("/materials/low")
async def low_stock():
    async with async_session() as session:
        res = await session.execute(
            select(Material).where(Material.stock < Material.min_stock)
        )
        return res.scalars().all()

# ----------- ORDERS -----------
@app.post("/orders")
async def create_order():
    """Vytvoří prázdnou objednávku"""
    async with async_session() as session:
        order = Order()
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order


@app.post("/orders/{order_id}/item")
async def add_item(order_id: int, material_id: int, quantity: float):
    """Přidá položku do objednávky"""
    async with async_session() as session:
        item = OrderItem(
            order_id=order_id,
            material_id=material_id,
            quantity=quantity,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item


@app.get("/orders")
async def list_orders():
    """Vrátí kompletní přehled všech objednávek včetně položek"""
    async with async_session() as session:
        result = await session.execute(
            select(Order).options(selectinload(Order.items))
        )
        orders = result.scalars().all()

        # načítáme položky ručně
        output = []
        for o in orders:
            await session.refresh(o)
            items = []
            for item in o.items:
                items.append({
                    "item_id": item.id,
                    "material_id": item.material_id,
                    "quantity": item.quantity
                })
            output.append({
                "order_id": o.id,
                "created_at": o.created_at,
                "items": items
            })
        return output