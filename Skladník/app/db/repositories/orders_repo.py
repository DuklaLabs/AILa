from app.db.models import Order, OrderItem, OrderStatus

class OrdersRepository:

    def __init__(self, session):
        self.session = session

    async def create_order(self):
        order = Order(status=OrderStatus.draft)
        self.session.add(order)
        await self.session.commit()
        await self.session.refresh(order)
        return order

    async def add_item(self, order_id, material_id, qty):
        item = OrderItem(order_id=order_id, material_id=material_id, quantity=qty)
        self.session.add(item)
        await self.session.commit()
        return item
