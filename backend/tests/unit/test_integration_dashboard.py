"""Integration tests for the Dashboard module.

Covers: overview, question-trend, exam-trend, recent-activity.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.auth import AuthService


def _create_user(db: Session, username: str, role: int = 1, menu_permissions=None) -> User:
    """Create a test user with upsert semantics."""
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        existing.role = role
        existing.menu_permissions = menu_permissions
        existing.status = 1
        db.commit()
        db.refresh(existing)
        return existing
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=AuthService.get_password_hash("Test123456!"),
        role=role,
        menu_permissions=menu_permissions,
        status=1,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client: TestClient, username: str) -> str:
    """Login and return access token."""
    resp = client.post("/api/auth/login/json", json={"username": username, "password": "Test123456!"})
    assert resp.status_code == 200
    body = resp.json()
    return body.get("data", body)["access_token"]


def _admin_token(client: TestClient, db: Session) -> str:
    _create_user(db, "dash_admin", role=1)
    return _login(client, "dash_admin")


def _student_token(client: TestClient, db: Session) -> str:
    _create_user(db, "dash_student", role=3)
    return _login(client, "dash_student")


class TestDashboardOverview:
    """GET /api/dashboard/overview - Get dashboard overview."""

    def test_get_overview_authenticated(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/dashboard/overview", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_overview_with_days_param(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/dashboard/overview?days=30", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_overview_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/dashboard/overview")
        assert resp.status_code == 401


class TestDashboardQuestionTrend:
    """GET /api/dashboard/question-trend - Get question trend."""

    def test_get_question_trend_week(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/dashboard/question-trend?period=week", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_question_trend_month(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/dashboard/question-trend?period=month", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_question_trend_year(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/dashboard/question-trend?period=year", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_question_trend_invalid_period(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/dashboard/question-trend?period=invalid", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 422

    def test_get_question_trend_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/dashboard/question-trend")
        assert resp.status_code == 401


class TestDashboardExamTrend:
    """GET /api/dashboard/exam-trend - Get exam trend."""

    def test_get_exam_trend_week(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/dashboard/exam-trend?period=week", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_exam_trend_month(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/dashboard/exam-trend?period=month", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_exam_trend_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/dashboard/exam-trend")
        assert resp.status_code == 401


class TestDashboardRecentActivity:
    """GET /api/dashboard/recent-activity - Get recent activity."""

    def test_get_recent_activity(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/dashboard/recent-activity", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_recent_activity_with_limit(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/dashboard/recent-activity?limit=5", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_recent_activity_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/dashboard/recent-activity")
        assert resp.status_code == 401
