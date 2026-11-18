import os
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.session import async_session, engine
from app.db.models import Base, Material, Order, OrderItem
from sqlalchemy.ext.asyncio import AsyncSession
from ailacore.auth import get_current_user
from ailacore.db import close_pool
from ailacore.models import User

# Shared Caddy gateway passes the full path through without stripping it
# (viz Gateway/Caddyfile) – každá backendová služba si musí svůj mount
# prefix ohlídat sama.
PREFIX = os.getenv("URL_PREFIX", "").rstrip("/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await close_pool()


app = FastAPI(title="Procurement Agent – Minimal Version", lifespan=lifespan)


@app.post(f"{PREFIX}/materials")
async def add_material(
    name: str,
    stock: float = 0,
    min_stock: float = 0,
    user: User = Depends(get_current_user),
):
    async with async_session() as session:
        material = Material(name=name, stock=stock, min_stock=min_stock)
        session.add(material)
        await session.commit()
        await session.refresh(material)
        return material


@app.get(f"{PREFIX}/materials")
async def list_materials(user: User = Depends(get_current_user)):
    async with async_session() as session:
        res = await session.execute(select(Material))
        return res.scalars().all()


@app.get(f"{PREFIX}/materials/low")
async def low_stock(user: User = Depends(get_current_user)):
    async with async_session() as session:
        res = await session.execute(
            select(Material).where(Material.stock < Material.min_stock)
        )
        return res.scalars().all()

# ----------- ORDERS -----------
@app.post(f"{PREFIX}/orders")
async def create_order(user: User = Depends(get_current_user)):
    """Vytvoří prázdnou objednávku"""
    async with async_session() as session:
        order = Order()
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return order


@app.post(f"{PREFIX}/orders/{{order_id}}/item")
async def add_item(
    order_id: int,
    material_id: int,
    quantity: float,
    user: User = Depends(get_current_user),
):
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


@app.get(f"{PREFIX}/orders")
async def list_orders(user: User = Depends(get_current_user)):
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