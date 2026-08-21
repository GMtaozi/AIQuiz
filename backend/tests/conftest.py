"""Shared pytest fixtures for the backend test suite."""

import os
import sys

import httpx
import pytest

# ---------------------------------------------------------------------------
# Environment must be set BEFORE any app modules are imported so that
# config validation passes and the engine uses the test database URL.
# ---------------------------------------------------------------------------
os.environ["TESTING"] = "true"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-do-not-use-in-production"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

# Ensure the backend package is importable when running pytest from repo root
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ---------------------------------------------------------------------------
# Now it's safe to import app internals
# ---------------------------------------------------------------------------
from app.database import Base, SessionLocal, engine
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Create all tables once per test session."""
    Base.metadata.create_all(bind=engine)
    yield
    # Teardown: drop all tables
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Provide a fresh database session with automatic rollback."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client():
    """TestClient fixture — 共享同进程 app，带 cookie jar（修复：原 ASGITransport
    写法与当前 httpx 版本不兼容，从未被现有测试真正使用过）。"""
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture()
async def async_client():
    """Async ASGITransport test client."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
