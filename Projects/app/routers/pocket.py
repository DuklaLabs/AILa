from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, UploadFile

from ailacore.auth import get_current_user
from ailacore.models import User

from app.services import pocket_bridge

router = APIRouter(prefix="/api/pocket", tags=["pocket"])


@router.get("/recordings")
async def list_recordings(
    page: int = 1, limit: int = 20, user: User = Depends(get_current_user)
):
    return await pocket_bridge.list_recordings(user, page=page, limit=limit)


@router.get("/recordings/{recording_id}")
async def get_recording(recording_id: str, user: User = Depends(get_current_user)):
    return await pocket_bridge.get_recording(user, recording_id)


@router.post("/recordings/upload")
async def upload_recording(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
):
    audio_bytes = await file.read()
    return await pocket_bridge.upload_recording(
        user,
        audio_bytes=audio_bytes,
        content_type=file.content_type or "audio/webm",
        title=title,
        file_name=file.filename,
    )


@router.post("/recordings/{recording_id}/extract-tasks")
async def extract_tasks(recording_id: str, user: User = Depends(get_current_user)):
    return await pocket_bridge.extract_task_candidates(user, recording_id)


@router.post("/recordings/{recording_id}/propose-tasks")
async def propose_tasks(
    recording_id: str, tasks: list[dict] = Body(...), user: User = Depends(get_current_user)
):
    return await pocket_bridge.propose_tasks(user, recording_id, tasks)
