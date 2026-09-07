"""
Route priority tests for knowledge router refactor.

Verifies that static paths (e.g. /trees, /statistics/summary, /category/{cat})
are correctly matched BEFORE the parameterized {knowledge_id} route.

IMPORTANT: Starlette matches routes by regex AND method. {knowledge_id} routes
are GET/PUT/DELETE while /import is POST, so even if /import comes after
{knowledge_id} in the route table, POST /api/knowledge/import will correctly
route to import_knowledge_points (method mismatch on {knowledge_id} routes).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User
from app.services.auth import AuthService

client = TestClient(app)


@pytest.fixture
def teacher_user(db: Session) -> User:
    """Create a teacher user for auth."""
    username = "route_priority_teacher"
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        db.delete(existing)
        db.commit()
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=AuthService.get_password_hash("test123456"),
        role=2,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_headers(teacher_user: User) -> dict:
    """Generate auth headers for the teacher user."""
    response = client.post(
        "/api/auth/login/json",
        json={"username": teacher_user.username, "password": "test123456"},
    )
    assert response.status_code == 200
    body = response.json()
    payload = body.get("data", body)
    token = payload["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestRoutePriority:
    """Verify that static paths take precedence over {knowledge_id} parameter."""

    def test_trees_not_captured_by_knowledge_id(self, auth_headers):
        """GET /api/knowledge/trees must resolve to get_knowledge_trees, not get_knowledge_point."""
        resp = client.get("/api/knowledge/trees", headers=auth_headers)
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body: {resp.text}"
        data = resp.json()
        inner = data.get("data", data)
        assert "trees" in inner, f"Expected 'trees' key in response, got: {list(inner.keys())}"
        assert "total" in inner, f"Expected 'total' key in response, got: {list(inner.keys())}"

    def test_statistics_summary_not_captured_by_knowledge_id(self, auth_headers):
        """GET /api/knowledge/statistics/summary must resolve to get_knowledge_statistics."""
        resp = client.get("/api/knowledge/statistics/summary", headers=auth_headers)
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body: {resp.text}"
        data = resp.json()
        inner = data.get("data", data)
        assert "total" in inner, f"Expected 'total' key, got: {list(inner.keys())}"
        assert "by_category" in inner, f"Expected 'by_category' key, got: {list(inner.keys())}"
        assert "by_exam_type" in inner, f"Expected 'by_exam_type' key, got: {list(inner.keys())}"

    def test_category_path_not_captured_by_knowledge_id(self, auth_headers):
        """GET /api/knowledge/category/default must resolve to get_by_category, not get_knowledge_point."""
        resp = client.get("/api/knowledge/category/default", headers=auth_headers)
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body: {resp.text}"
        data = resp.json()
        inner = data.get("data", data)
        assert "items" in inner, f"Expected 'items' key, got: {list(inner.keys())}"

    def test_question_counts_not_captured_by_knowledge_id(self, auth_headers):
        """POST /api/knowledge/question-counts must resolve to get_knowledge_point_question_counts."""
        resp = client.post(
            "/api/knowledge/question-counts",
            json={"knowledge_ids": []},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body: {resp.text}"

    def test_hierarchy_trees_not_captured(self, auth_headers):
        """GET /api/knowledge/hierarchy-trees must resolve to get_knowledge_hierarchy_trees."""
        resp = client.get("/api/knowledge/hierarchy-trees", headers=auth_headers)
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body: {resp.text}"
        data = resp.json()
        inner = data.get("data", data)
        assert "trees" in inner, f"Expected 'trees' key, got: {list(inner.keys())}"

    def test_root_list_path(self, auth_headers):
        """GET /api/knowledge/ must resolve to get_knowledge_list."""
        resp = client.get("/api/knowledge/", headers=auth_headers)
        assert resp.status_code == 200, f"Unexpected status: {resp.status_code}, body: {resp.text}"
        data = resp.json()
        inner = data.get("data", data)
        assert "items" in inner, f"Expected 'items' key, got: {list(inner.keys())}"
        assert "total" in inner, f"Expected 'total' key, got: {list(inner.keys())}"

    def test_knowledge_id_path_still_works(self, auth_headers):
        """GET /api/knowledge/99999 should still resolve to get_knowledge_point (returning 404)."""
        resp = client.get("/api/knowledge/99999", headers=auth_headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}, body: {resp.text}"
