from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ailacore.auth import get_current_user
from ailacore.models import User

from app.services import time_tracking

router = APIRouter(prefix="/api", tags=["time"])


class StartIn(BaseModel):
    note: Optional[str] = None


class StopIn(BaseModel):
    entry_id: Optional[int] = None


class ManualIn(BaseModel):
    minutes: int
    started_at: Optional[datetime] = None
    note: Optional[str] = None


@router.get("/tasks/{task_id}/time")
async def list_time(
    task_id: int,
    user_id: Optional[int] = None,
    user: User = Depends(get_current_user),
):
    return await time_tracking.list_time_entries(
        user, task_id=task_id, target_user_id=user_id
    )


@router.post("/tasks/{task_id}/time/start", status_code=201)
async def start(task_id: int, body: StartIn, user: User = Depends(get_current_user)):
    return await time_tracking.start_timer(user, task_id, body.note)


@router.post("/tasks/{task_id}/time/manual", status_code=201)
async def manual(task_id: int, body: ManualIn, user: User = Depends(get_current_user)):
    return await time_tracking.add_manual_entry(
        user, task_id, minutes=body.minutes, started_at=body.started_at, note=body.note
    )


@router.post("/time/stop")
async def stop(body: StopIn, user: User = Depends(get_current_user)):
    return await time_tracking.stop_timer(user, body.entry_id)


@router.get("/time/running")
async def running(user: User = Depends(get_current_user)):
    return await time_tracking.running_timer(user)
