from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from datetime import datetime

Base = declarative_base()


class Material(Base):
    __tablename__ = "materials"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    stock = Column(Float, default=0)       # aktuální množství
    min_stock = Column(Float, default=0)   # minimální zásoba
    unit = Column(String, default="pcs")   # jednotka (kg, L, ks, ...)
    created_at = Column(DateTime, default=datetime.utcnow)


class MaterialMovement(Base):
    __tablename__ = "material_movements"

    id = Column(Integer, primary_key=True)
    material_id = Column(Integer, ForeignKey("materials.id"), nullable=False)
    change = Column(Float, nullable=False)  # +příjem, -výdej
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    material = relationship("Material")
