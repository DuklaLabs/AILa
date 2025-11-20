from sqlalchemy.orm import Session
from ..db.repositories import materials_repo


def list_materials(db: Session, skip: int = 0, limit: int = 100):
    return materials_repo.list_materials(db, skip=skip, limit=limit)


def create_material(db: Session, name: str, unit_price: float, supplier_id: int = None):
    return materials_repo.create_material(db, name=name, unit_price=unit_price, supplier_id=supplier_id)
