"""Knowledge Router Package - Aggregates tree, CRUD, statistics, AI analysis,batch, questions, and import sub-routers.

Each sub-module owns a distinct slice of the /api/knowledge surface. Route
registration order mirrors the original monolithic knowledge.py so that static
paths (e.g. ``/trees``) are registered before parameterized paths
(e.g. ``/{knowledge_id}``), preserving the original matching behavior.
"""

from fastapi import APIRouter

from app.routers.knowledge.ai_analysis import router as ai_analysis_router
from app.routers.knowledge.batch import router as batch_router
from app.routers.knowledge.crud import router as crud_router
from app.routers.knowledge.import_file import router as import_file_router
from app.routers.knowledge.questions import router as questions_router
from app.routers.knowledge.statistics import router as statistics_router
from app.routers.knowledge.tree_routes import router as tree_routes_router

router = APIRouter()
router.include_router(tree_routes_router)
router.include_router(crud_router)
router.include_router(statistics_router)
router.include_router(ai_analysis_router)
router.include_router(batch_router)
router.include_router(questions_router)
router.include_router(import_file_router)
