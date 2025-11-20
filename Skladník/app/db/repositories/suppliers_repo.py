class OrderService:

    def __init__(self, materials_repo, orders_repo):
        self.materials = materials_repo
        self.orders = orders_repo

    async def auto_generate_order(self):
        low_stock = await self.materials.get_below_min_stock()

        if not low_stock:
            return None

        order = await self.orders.create_order()

        for m in low_stock:
            missing = max(m.min_stock - m.stock, 0)
            await self.orders.add_item(order.id, m.id, missing)

        return order
