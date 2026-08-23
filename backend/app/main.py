"""FastAPI Application Entry Point"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.routers import (
    ai_templates,
    audit,
    auth,
    chapters,
    dashboard,
    exam_records,
    exams,
    knowledge,
    knowledge_bases,
    notifications,
    paper_template,
    paper_versions,
    papers,
    questions,
    subjects,
    system,
)
from app.utils.exceptions import global_exception_handler, http_exception_handler, validation_exception_handler
from app.utils.response import wrap_response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks.

    NOTE: 表结构由 Alembic 管理，请先运行 `alembic upgrade head`。
    此处仅做日志记录，不再调用 create_all（避免绕过版本表）。
    另：初始化默认系统设置到 DB（仅一次，避免每个请求都跑 init_default_settings）。
    """
    # ---- startup ----
    from app.observability import init_sentry, setup_logging

    setup_logging(debug=settings.debug, json_format=settings.log_json)
    init_sentry(settings.sentry_dsn, settings.environment)
    # 商业授权加载（无效/缺失自动进入试用模式，不阻塞启动）
    try:
        from app.database import SessionLocal as _SessionLocal
        from app.services.license_service import license_service

        _db = _SessionLocal()
        try:
            license_service.load(_db)
        finally:
            _db.close()
    except Exception as e:
        logging.getLogger(__name__).warning(f"License 加载失败（进入试用判定）: {e}")
    try:
        from app.database import SessionLocal
        from app.routers.system import init_default_settings

        db = SessionLocal()
        try:
            init_default_settings(db)
        finally:
            db.close()
        logging.getLogger(__name__).info("默认系统设置已初始化")
    except Exception as e:
        logging.getLogger(__name__).warning(f"初始化系统设置失败（可忽略，将回落默认值）: {e}")
    logging.getLogger(__name__).info("应用启动完成")

    yield

    # ---- shutdown (placeholder for future cleanup) ----
    logging.getLogger(__name__).info("应用关闭")


app = FastAPI(
    title="智题 AIQuiz",
    version="1.0.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
    lifespan=lifespan,
)


# CORS configuration - origins must be explicitly set
# In production, configure trusted origins via CORS_ORIGINS environment variable
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
else:
    # 评估 P2-18：未配置显式 CORS 来源时，仅放行同源请求（不返回
    # Access-Control-Allow-Origin: null——该值会破坏同源凭据并招致浏览器拒绝）。
    @app.middleware("http")
    async def restrict_cors(request: Request, call_next):
        if request.method == "OPTIONS":
            return JSONResponse(
                status_code=200,
                headers={"Allow": "GET, POST, PUT, DELETE, OPTIONS"},
            )
        return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def unify_response_middleware(request: Request, call_next):
    """Wrap successful JSON responses in the standard envelope."""
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("application/json"):
        # 必须 await：wrap_response 是协程，否则中间件返回 coroutine 导致
        # TypeError: 'coroutine' object is not callable（所有 JSON 接口崩溃）
        return await wrap_response(request, response)
    return response


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(subjects.router, prefix="/api/subjects", tags=["subjects"])
app.include_router(chapters.router, prefix="/api/chapters", tags=["chapters"])
app.include_router(questions.router, prefix="/api/questions", tags=["questions"])
app.include_router(ai_templates.router, prefix="/api/ai", tags=["ai"])
app.include_router(papers.router, prefix="/api/papers", tags=["papers"])
app.include_router(paper_versions.router, prefix="/api/paper-versions", tags=["paper-versions"])
app.include_router(exams.router, prefix="/api/exams", tags=["exams"])
app.include_router(exam_records.router, prefix="/api/exam-records", tags=["exam_records"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(knowledge_bases.router, prefix="/api/knowledge-bases", tags=["knowledge-bases"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(paper_template.router, prefix="/api/paper-templates", tags=["paper-templates"])


@app.get("/")
async def root():
    return {"message": "AI Question System API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ============ Exception handlers ============

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)
