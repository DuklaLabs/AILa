from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.repositories.materials_repo import MaterialsRepository
from app.db.repositories.orders_repo import OrdersRepository
from app.services.order_service import OrderService

router = APIRouter()

@router.post("/auto")
async def auto_generate_order(db: AsyncSession = Depends(get_db)):
    materials_repo = MaterialsRepository(db)
    orders_repo = OrdersRepository(db)
    service = OrderService(materials_repo, orders_repo)
    order = await service.create_order_for_low_stock()
    return order
