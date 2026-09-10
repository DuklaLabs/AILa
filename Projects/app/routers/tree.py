from datetime import date
from typing import Optional

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel

from ailacore.auth import get_current_user
from ailacore.models import User

from app.services import tree

router = APIRouter(prefix="/api", tags=["projects"])


class ProjectIn(BaseModel):
    folder_id: int
    name: str
    description: Optional[str] = None
    planned_budget_czk: Optional[float] = None
    started_on: Optional[date] = None
    due_on: Optional[date] = None
    lead_user_id: Optional[int] = None


@router.get("/workspaces")
async def list_workspaces(user: User = Depends(get_current_user)):
    return await tree.list_workspaces(user)


@router.get("/folders")
async def list_folders(
    workspace_id: Optional[int] = None, user: User = Depends(get_current_user)
):
    return await tree.list_folders(user, workspace_id=workspace_id)


@router.get("/projects")
async def list_projects(
    folder_id: Optional[int] = None,
    status: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    return await tree.list_projects(user, folder_id=folder_id, status=status)


@router.post("/projects", status_code=201)
async def create_project(body: ProjectIn, user: User = Depends(get_current_user)):
    return await tree.create_project(user, **body.model_dump())


@router.get("/projects/{project_id}")
async def get_project(project_id: int, user: User = Depends(get_current_user)):
    return await tree.get_project(user, project_id)


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: int,
    fields: dict = Body(...),
    user: User = Depends(get_current_user),
):
    return await tree.update_project(user, project_id, fields)


@router.delete("/projects/{project_id}")
async def delete_project(project_id: int, user: User = Depends(get_current_user)):
    return await tree.delete_project(user, project_id)


@router.get("/projects/{project_id}/phases")
async def list_phases(project_id: int, user: User = Depends(get_current_user)):
    return await tree.list_phases(user, project_id)
