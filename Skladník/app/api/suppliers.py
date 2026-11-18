from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.session import get_db
from ..db.repositories import suppliers_repo

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("/", response_model=List[dict])
async def read_suppliers(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    items = await suppliers_repo.list_suppliers(db, skip=skip, limit=limit)
    return [{"id": s.id, "name": s.name, "contact": s.contact} for s in items]


@router.post("/", response_model=dict)
async def create_supplier(payload: dict, db: AsyncSession = Depends(get_db)):
    name = payload.get("name")
    contact = payload.get("contact")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    s = await suppliers_repo.create_supplier(db, name=name, contact=contact)
    return {"id": s.id, "name": s.name}


@router.get("/{supplier_id}", response_model=dict)
async def get_supplier(supplier_id: int, db: AsyncSession = Depends(get_db)):
    s = await suppliers_repo.get_supplier(db, supplier_id)
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return {"id": s.id, "name": s.name, "contact": s.contact}
