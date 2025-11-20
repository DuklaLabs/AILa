from fastapi import APIRouter
from app.services.order_service import OrderService

router = APIRouter()

@router.post("/auto")
async def auto_generate_order():
    service = OrderService(...)
    order = await service.auto_generate_order()
    return order
