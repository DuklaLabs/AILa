# app/services/order_service.py
from app.db.repositories.materials_repo import MaterialsRepository
from app.db.repositories.orders_repo import OrdersRepository

class OrderService:
    def __init__(self, materials_repo: MaterialsRepository, orders_repo: OrdersRepository):
        self.materials = materials_repo
        self.orders = orders_repo

    async def create_order_for_low_stock(self):
        low_items = await self.materials.get_below_min_stock()

        if not low_items:
            return None

        order = await self.orders.create_order()

        for material in low_items:
            missing_amount = max(material.min_stock - material.stock, 0)
            await self.orders.add_item(order.id, material.id, missing_amount)

        return order
