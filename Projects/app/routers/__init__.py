"""HTTP routery služby Projects – tenké obaly nad `app/services/`."""
from fastapi import APIRouter

from app.routers.costs import router as costs_router
from app.routers.people import router as people_router
from app.routers.pocket import router as pocket_router
from app.routers.proposals import router as proposals_router
from app.routers.tasks import router as tasks_router
from app.routers.time_tracking import router as time_router
from app.routers.tree import router as tree_router

api_router = APIRouter()
api_router.include_router(tree_router)
api_router.include_router(tasks_router)
api_router.include_router(time_router)
api_router.include_router(costs_router)
api_router.include_router(proposals_router)
api_router.include_router(people_router)
api_router.include_router(pocket_router)
