from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ailacore.auth import get_current_user
from ailacore.models import User

from app.services import proposals

router = APIRouter(prefix="/api", tags=["proposals"])


class ReviewIn(BaseModel):
    note: Optional[str] = None


@router.get("/proposals")
async def list_proposals(
    status: str = "pending", user: User = Depends(get_current_user)
):
    return await proposals.list_proposals(user, status=status)


@router.post("/proposals/{proposal_id}/approve")
async def approve(
    proposal_id: int, body: ReviewIn = ReviewIn(), user: User = Depends(get_current_user)
):
    return await proposals.review_proposal(
        user, proposal_id, approve=True, note=body.note
    )


@router.post("/proposals/{proposal_id}/reject")
async def reject(
    proposal_id: int, body: ReviewIn = ReviewIn(), user: User = Depends(get_current_user)
):
    return await proposals.review_proposal(
        user, proposal_id, approve=False, note=body.note
    )
