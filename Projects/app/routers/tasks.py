from datetime import date
from typing import Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from ailacore.auth import get_current_user
from ailacore.models import User

from app.services import tasks

router = APIRouter(prefix="/api", tags=["tasks"])


class TaskIn(BaseModel):
    phase_id: int
    title: str
    description: Optional[str] = None
    assignee_user_id: Optional[int] = None
    status: str = "backlog"
    start_on: Optional[date] = None
    due_on: Optional[date] = None
    proto_version: Optional[str] = None
    estimated_hours: Optional[float] = None
    cost_type: Optional[str] = None
    estimated_cost_czk: Optional[float] = None
    actual_cost_czk: Optional[float] = None
    order_status: Optional[str] = None


class StatusIn(BaseModel):
    status: str


class AssigneeIn(BaseModel):
    assignee_user_id: Optional[int] = None


class CollaboratorsIn(BaseModel):
    user_ids: list[int] = []


class DependencyIn(BaseModel):
    depends_on_task_id: int


@router.get("/phases/{phase_id}/tasks")
async def list_phase_tasks(phase_id: int, user: User = Depends(get_current_user)):
    return await tasks.list_tasks(user, phase_id=phase_id)


@router.get("/tasks")
async def list_tasks(
    phase_id: Optional[int] = None,
    project_id: Optional[int] = None,
    user: User = Depends(get_current_user),
):
    return await tasks.list_tasks(user, phase_id=phase_id, project_id=project_id)


@router.post("/tasks", status_code=201)
async def create_task(body: TaskIn, user: User = Depends(get_current_user)):
    return await tasks.create_task(user, **body.model_dump())


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, user: User = Depends(get_current_user)):
    return await tasks.get_task(user, task_id)


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int, fields: dict = Body(...), user: User = Depends(get_current_user)
):
    return await tasks.update_task(user, task_id, fields)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, user: User = Depends(get_current_user)):
    return await tasks.delete_task(user, task_id)


@router.post("/tasks/{task_id}/status")
async def set_status(task_id: int, body: StatusIn, user: User = Depends(get_current_user)):
    return await tasks.set_task_status(user, task_id, body.status)


@router.post("/tasks/{task_id}/assignee")
async def set_assignee(task_id: int, body: AssigneeIn, user: User = Depends(get_current_user)):
    return await tasks.set_task_assignee(user, task_id, body.assignee_user_id)


@router.put("/tasks/{task_id}/collaborators")
async def set_collaborators(
    task_id: int, body: CollaboratorsIn, user: User = Depends(get_current_user)
):
    return await tasks.set_task_collaborators(user, task_id, body.user_ids)


@router.post("/tasks/{task_id}/dependencies")
async def add_dependency(
    task_id: int, body: DependencyIn, user: User = Depends(get_current_user)
):
    return await tasks.add_task_dependency(user, task_id, body.depends_on_task_id)


@router.delete("/tasks/{task_id}/dependencies/{depends_on_task_id}")
async def remove_dependency(
    task_id: int, depends_on_task_id: int, user: User = Depends(get_current_user)
):
    return await tasks.remove_task_dependency(user, task_id, depends_on_task_id)
