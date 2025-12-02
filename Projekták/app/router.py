from fastapi import APIRouter
from app.agent import process_task

router = APIRouter()

@router.post("/task")
def handle_task(data: dict):
    return process_task(data)