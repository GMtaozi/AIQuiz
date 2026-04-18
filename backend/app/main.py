"""FastAPI Application Entry Point"""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import auth, subjects, chapters, questions, ai_templates, papers, exams, exam_records
from app.routers import audit, dashboard, knowledge, system, paper_template, notifications
from app.config import settings

# 确保所有模型被导入，以便 init_db() 能创建对应的表
import app.models.question  # noqa: F401
import app.models.knowledge  # noqa: F401
import app.models.user  # noqa: F401
import app.models.notification  # noqa: F401
import app.models.system_setting  # noqa: F401
import app.models.paper_template  # noqa: F401
import app.models.password_reset  # noqa: F401

# 配置日志：确保app模块的logger输出INFO级别
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)

app = FastAPI(title="智题 AIQuiz", version="1.0.0")


@app.on_event("startup")
async def startup():
    """启动时初始化数据库表（自动创建新表，不影响已有数据）"""
    from app.database import init_db
    init_db()
    logging.getLogger(__name__).info("数据库表初始化完成")

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
    # Only allow credentialed requests from same origin if no explicit origins set
    @app.middleware("http")
    async def restrict_cors(request: Request, call_next):
        if request.method == "OPTIONS":
            return JSONResponse(
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": "null",
                    "Access-Control-Allow-Credentials": "false",
                }
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

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(subjects.router, prefix="/api/subjects", tags=["subjects"])
app.include_router(chapters.router, prefix="/api/chapters", tags=["chapters"])
app.include_router(questions.router, prefix="/api/questions", tags=["questions"])
app.include_router(ai_templates.router, prefix="/api/ai", tags=["ai"])
app.include_router(papers.router, prefix="/api/papers", tags=["papers"])
app.include_router(exams.router, prefix="/api/exams", tags=["exams"])
app.include_router(exam_records.router, prefix="/api/exam-records", tags=["exam_records"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(paper_template.router, prefix="/api/paper-templates", tags=["paper-templates"])


@app.get("/")
async def root():
    return {"message": "AI Question System API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}