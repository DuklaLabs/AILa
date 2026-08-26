from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class User(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    is_active: bool


class RFIDCard(BaseModel):
    id: int
    user_id: int
    card_uid: str
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    is_active: bool
