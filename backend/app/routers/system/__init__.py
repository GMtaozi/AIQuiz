"""System Router Package - Aggregates settings, exam_types, and users sub-routers.

Also re-exports helpers for backward compatibility (used by main.py and settings_service.py).
"""

from fastapi import APIRouter

from app.routers.system.exam_types import router as exam_types_router
from app.routers.system.license import router as license_router
from app.routers.system.settings import router as settings_router
from app.routers.system.users import router as users_router

router = APIRouter()
router.include_router(settings_router)
router.include_router(exam_types_router)
router.include_router(users_router)
router.include_router(license_router)

# Re-export helpers for backward compatibility (used by main.py, settings_service.py, auth.py)
from app.routers.system._helpers import (
    DEFAULT_SETTINGS,
    _validate_password_strength,
    get_ai_config,
    get_role_permissions_config,
    get_setting_from_db,
    init_default_settings,
    save_role_permissions,
)
from app.services.settings_service import get_security_settings
