# app/db/models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .base import Base


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    stock = Column(Float, default=0)
    min_stock = Column(Float, default=0)
    unit = Column(String, default="pcs")
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))

    supplier = relationship("Supplier", back_populates="materials")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    contact = Column(String, nullable=True)
    website = Column(String, nullable=True)

    materials = relationship("Material", back_populates="supplier")


class OrderStatus(enum.Enum):
    draft = "draft"
    created = "created"
    sent = "sent"
    received = "received"
    canceled = "canceled"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(OrderStatus), default=OrderStatus.draft)
    note = Column(String, nullable=True)

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    material_id = Column(Integer, ForeignKey("materials.id"))
    quantity = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    material = relationship("Material")
