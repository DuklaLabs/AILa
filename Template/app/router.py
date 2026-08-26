from fastapi import APIRouter, Depends

from ailacore.auth import get_current_user, require_role
from ailacore.models import User

from app.agent import process_task

router = APIRouter()


@router.post("/task")
async def handle_task(data: dict):
    return await process_task(data)


# Vzor: chráněná routa dostupná každému přihlášenému uživateli
# (přes RFID kartu nebo heslo — obojí vydá stejný ailacore token).
@router.get("/whoami")
async def whoami(user: User = Depends(get_current_user)):
    return user


# Vzor: routa omezená jen na konkrétní roli.
@router.get("/admin-only", dependencies=[Depends(require_role("admin", "staff"))])
async def admin_only():
    return {"status": "ok"}
