from typing import Optional

from fastapi import APIRouter, Depends

from ailacore.auth import get_current_user
from ailacore.models import User

from app.services import people

router = APIRouter(prefix="/api", tags=["people"])


@router.get("/users")
async def list_users(q: Optional[str] = None, user: User = Depends(get_current_user)):
    return await people.list_people(user, q=q)
