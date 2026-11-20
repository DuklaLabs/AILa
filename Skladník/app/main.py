import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from app.session import async_session, engine
from app.db.models import Base, Material, Order, OrderItem, OrderStatus
from app.pages import objednavky_page, sklad_page
from ailacore.auth import SESSION_COOKIE, get_current_user, get_user_from_token
from ailacore.db import close_pool
from ailacore.models import User

# Shared Caddy gateway passes the full path through without stripping it
# (viz Gateway/Caddyfile) – každá backendová služba si musí svůj mount
# prefix ohlídat sama.
PREFIX = os.getenv("URL_PREFIX", "").rstrip("/")

STATIC_DIR = Path(__file__).parent / "static"

# Sloupce, které create_all u už existující SQLite tabulky nedoplní.
_ADDED_COLUMNS = {
    "materials": {"category": "VARCHAR", "unit": "VARCHAR"},
    "orders": {"status": "VARCHAR", "note": "VARCHAR"},
}


def _add_missing_columns(sync_conn):
    for table, cols in _ADDED_COLUMNS.items():
        have = {row[1] for row in sync_conn.execute(text(f"PRAGMA table_info({table})"))}
        for col, ddl in cols.items():
            if have and col not in have:
                sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
    yield
    await close_pool()


app = FastAPI(title="Procurement Agent – Minimal Version", lifespan=lifespan)

# Sdílená UI knihovna (theme.css/ui.css/ui.js/theme-toggle.js) + sklad.css/js.
app.mount(f"{PREFIX}/static", StaticFiles(directory=STATIC_DIR), name="static")


# ----------- HTML MODULY -----------
async def _html_user(request: Request) -> Optional[User]:
    """Uživatel z cookie/Bearer pro HTML stránky – na rozdíl od get_current_user
    nehází 401, ale vrací None (stránka pak přesměruje na přihlášení)."""
    token = request.cookies.get(SESSION_COOKIE)
    if token is None:
        auth = request.headers.get("authorization") or ""
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ")
    return await get_user_from_token(token)


def _login_redirect(request: Request) -> RedirectResponse:
    target = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return RedirectResponse(f"/access/login?next={quote(target, safe='')}", status_code=303)


@app.get(f"{PREFIX}/", response_class=HTMLResponse)
async def sklad_html(request: Request):
    if await _html_user(request) is None:
        return _login_redirect(request)
    return HTMLResponse(sklad_page(PREFIX))


@app.get(f"{PREFIX}/objednavky/", response_class=HTMLResponse)
async def objednavky_html(request: Request):
    if await _html_user(request) is None:
        return _login_redirect(request)
    return HTMLResponse(objednavky_page(PREFIX))


# ----------- MATERIALS -----------
@app.post(f"{PREFIX}/materials")
async def add_material(
    name: str,
    stock: float = 0,
    min_stock: float = 0,
    category: Optional[str] = None,
    unit: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    async with async_session() as session:
        material = Material(
            name=name,
            stock=stock,
            min_stock=min_stock,
            category=(category or "").strip() or None,
            unit=(unit or "").strip() or "pcs",
        )
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
def _status_value(order: Order) -> str:
    return (order.status or OrderStatus.draft).value


@app.post(f"{PREFIX}/orders")
async def create_order(
    note: Optional[str] = None,
    status: str = OrderStatus.draft.value,
    user: User = Depends(get_current_user),
):
    """Vytvoří prázdnou objednávku (volitelně s poznámkou a počátečním stavem)."""
    try:
        st = OrderStatus(status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown status: {status}")
    async with async_session() as session:
        order = Order(note=(note or "").strip() or None, status=st)
        session.add(order)
        await session.commit()
        await session.refresh(order)
        return {
            "id": order.id,
            "order_id": order.id,
            "created_at": order.created_at,
            "status": _status_value(order),
            "note": order.note,
        }


@app.post(f"{PREFIX}/orders/{{order_id}}/status")
async def set_order_status(
    order_id: int,
    status: str,
    user: User = Depends(get_current_user),
):
    """Změní stav objednávky (draft/created/sent/received/canceled)."""
    try:
        st = OrderStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown status: {status}. Allowed: {[s.value for s in OrderStatus]}",
        )
    async with async_session() as session:
        order = await session.get(Order, order_id)
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found")
        order.status = st
        await session.commit()
        return {"order_id": order.id, "status": st.value}


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
    """Vrátí kompletní přehled všech objednávek včetně položek a stavu"""
    async with async_session() as session:
        result = await session.execute(
            select(Order).options(selectinload(Order.items).selectinload(OrderItem.material))
        )
        output = []
        for o in result.scalars().all():
            items = []
            for item in o.items:
                items.append({
                    "item_id": item.id,
                    "material_id": item.material_id,
                    "material_name": item.material.name if item.material else None,
                    "unit": item.material.unit if item.material else None,
                    "quantity": item.quantity,
                })
            output.append({
                "order_id": o.id,
                "created_at": o.created_at,
                "status": _status_value(o),
                "note": o.note,
                "items": items,
            })
        return output
