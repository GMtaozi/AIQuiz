"""Questions Router Package - Aggregates CRUD and Import/Export sub-routers

注意：静态路径（/export、/similarity-check、/statistics）必须先于 crud 的参数化
路由（/{question_id}）注册，否则会被遮蔽导致 422。
"""

from fastapi import APIRouter

from app.routers.questions.crud import router as crud_router
from app.routers.questions.export import router as export_router
from app.routers.questions.import_ import router as import_router
from app.routers.questions.similarity import router as similarity_router

router = APIRouter()
router.include_router(similarity_router)
router.include_router(export_router)
router.include_router(import_router)
router.include_router(crud_router)
