from typing import Optional

from fastapi import APIRouter, Depends

from ailacore.auth import get_current_user
from ailacore.models import User

from app.services import costs

router = APIRouter(prefix="/api", tags=["costs"])


@router.get("/projects/{project_id}/costs")
async def project_costs(
    project_id: int,
    proto_version: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    return await costs.project_costs(user, project_id, proto_version=proto_version)
