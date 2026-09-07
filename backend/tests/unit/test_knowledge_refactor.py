"""Tests to verify knowledge.py refactoring preserves API contract.

This test file verifies that the refactored knowledge subpackage maintains
the same API endpoints, HTTP methods, and response structures as the original
monolithic knowledge.py file.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgePoint
from app.models.user import User
from app.services.auth import AuthService


def _create_user(db: Session, username: str, role: int = 1) -> User:
    """Create a test user."""
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        existing.role = role
        db.commit()
        db.refresh(existing)
        return existing
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=AuthService.get_password_hash("Test123456!"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client: TestClient, username: str) -> str:
    """Login and return token."""
    resp = client.post("/api/auth/login/json", json={"username": username, "password": "Test123456!"})
    assert resp.status_code == 200
    body = resp.json()
    return body.get("data", body)["access_token"]


def _admin_token(client: TestClient, db: Session) -> str:
    """Get admin token."""
    _create_user(db, "knowledge_admin", role=1)
    return _login(client, "knowledge_admin")


class TestKnowledgeRoutesExist:
    """Verify all knowledge routes are registered with correct methods."""

    def test_trees_endpoint_exists(self, client: TestClient, db: Session):
        """GET /api/knowledge/trees should exist."""
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge/trees", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert "trees" in data
        assert "total" in data

    def test_hierarchy_trees_endpoint_exists(self, client: TestClient, db: Session):
        """GET /api/knowledge/hierarchy-trees should exist."""
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge/hierarchy-trees", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert "trees" in data

    def test_list_endpoint_exists(self, client: TestClient, db: Session):
        """GET /api/knowledge/ should exist."""
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert "items" in data
        assert "total" in data

    def test_statistics_endpoint_exists(self, client: TestClient, db: Session):
        """GET /api/knowledge/statistics/summary should exist."""
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge/statistics/summary", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert "total" in data
        assert "by_category" in data
        assert "by_exam_type" in data
        assert "max_depth" in data

    def test_category_endpoint_exists(self, client: TestClient, db: Session):
        """GET /api/knowledge/category/{category} should exist."""
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge/category/default", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert "items" in data
        assert "total" in data


class TestKnowledgeCRUD:
    """Verify CRUD operations work correctly after refactoring."""

    def test_create_knowledge_point(self, client: TestClient, db: Session):
        """POST /api/knowledge/ should create a knowledge point."""
        token = _admin_token(client, db)
        resp = client.post(
            "/api/knowledge/",
            json={"name": "Test KP", "description": "Test description"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        data = resp.json().get("data", resp.json())
        assert data["name"] == "Test KP"
        assert data["description"] == "Test description"
        assert "id" in data

    def test_get_knowledge_point(self, client: TestClient, db: Session):
        """GET /api/knowledge/{id} should return knowledge point details."""
        token = _admin_token(client, db)
        # Create a knowledge point first
        kp = KnowledgePoint(name="Get Test KP", status=1, created_by=1)
        db.add(kp)
        db.commit()
        db.refresh(kp)

        resp = client.get(f"/api/knowledge/{kp.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["name"] == "Get Test KP"
        assert "children_count" in data

    def test_update_knowledge_point(self, client: TestClient, db: Session):
        """PUT /api/knowledge/{id} should update a knowledge point."""
        token = _admin_token(client, db)
        # Create a knowledge point first
        kp = KnowledgePoint(name="Update Test KP", status=1, created_by=1)
        db.add(kp)
        db.commit()
        db.refresh(kp)

        resp = client.put(
            f"/api/knowledge/{kp.id}",
            json={"name": "Updated KP"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["name"] == "Updated KP"

    def test_delete_knowledge_point(self, client: TestClient, db: Session):
        """DELETE /api/knowledge/{id} should delete a knowledge point."""
        token = _admin_token(client, db)
        # Create a knowledge point first
        kp = KnowledgePoint(name="Delete Test KP", status=1, created_by=1)
        db.add(kp)
        db.commit()
        db.refresh(kp)

        resp = client.delete(f"/api/knowledge/{kp.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["message"] == "删除成功"

    def test_get_nonexistent_knowledge_point(self, client: TestClient, db: Session):
        """GET /api/knowledge/{id} should return 404 for nonexistent ID."""
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404


class TestKnowledgeQuestionEndpoints:
    """Verify question-related endpoints work correctly."""

    def test_question_counts_endpoint(self, client: TestClient, db: Session):
        """POST /api/knowledge/question-counts should return question counts."""
        token = _admin_token(client, db)
        # Create a knowledge point
        kp = KnowledgePoint(name="QC Test KP", status=1, created_by=1)
        db.add(kp)
        db.commit()
        db.refresh(kp)

        resp = client.post(
            "/api/knowledge/question-counts",
            json={"knowledge_ids": [kp.id]},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert str(kp.id) in data

    def test_knowledge_questions_endpoint(self, client: TestClient, db: Session):
        """GET /api/knowledge/{id}/questions should return questions."""
        token = _admin_token(client, db)
        # Create a knowledge point
        kp = KnowledgePoint(name="Questions Test KP", status=1, created_by=1)
        db.add(kp)
        db.commit()
        db.refresh(kp)

        resp = client.get(f"/api/knowledge/{kp.id}/questions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert "questions" in data
        assert "total" in data


class TestKnowledgeImportEndpoint:
    """Verify import endpoint works correctly."""

    def test_import_json(self, client: TestClient, db: Session):
        """POST /api/knowledge/import should import JSON file."""
        import json
        token = _admin_token(client, db)
        
        data = [
            {"name": "Import Test KP 1", "description": "Description 1"},
            {"name": "Import Test KP 2", "description": "Description 2"},
        ]
        
        resp = client.post(
            "/api/knowledge/import",
            files={"file": ("test.json", json.dumps(data), "application/json")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, f"Import failed: {resp.text}"
        result = resp.json().get("data", resp.json())
        assert result["success"] is True
        assert result["created_count"] == 2
