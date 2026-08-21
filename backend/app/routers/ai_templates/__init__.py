"""AI Templates Router package - template CRUD + question generation + async tasks."""

from fastapi import APIRouter

from app.routers.ai_templates.crud import router as crud_router
from app.routers.ai_templates.generation import router as generation_router
from app.routers.ai_templates.tasks import router as tasks_router

router = APIRouter()
router.include_router(crud_router)
router.include_router(generation_router)
router.include_router(tasks_router)
