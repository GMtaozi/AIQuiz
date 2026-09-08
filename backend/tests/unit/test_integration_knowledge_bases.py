"""Integration tests for the Knowledge Bases module.

Covers: KB CRUD, entries listing, points listing, upload (mocked).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeBase, KnowledgeEntry, KnowledgePoint
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
    _create_user(db, "kb_admin", role=1)
    return _login(client, "kb_admin")


def _teacher_token(client: TestClient, db: Session) -> str:
    _create_user(db, "kb_teacher", role=2)
    return _login(client, "kb_teacher")


def _student_token(client: TestClient, db: Session) -> str:
    _create_user(db, "kb_student", role=3)
    return _login(client, "kb_student")


def _create_knowledge_base(db: Session, user_id: int, visibility: str = "public") -> KnowledgeBase:
    """Create a test knowledge base."""
    kb = KnowledgeBase(
        name="Test KB",
        description="Test knowledge base",
        subject_id=1,
        category="default",
        visibility=visibility,
        status=1,
        created_by=user_id,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


class TestKnowledgeBaseList:
    """GET /api/knowledge-bases/ - List knowledge bases."""

    def test_list_kbs_authenticated(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge-bases/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_kbs_with_filters(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge-bases/?keyword=Test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_kbs_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/knowledge-bases/")
        assert resp.status_code == 401


class TestKnowledgeBaseDetail:
    """GET /api/knowledge-bases/{kb_id} - Get knowledge base details."""

    def test_get_kb_detail_public(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        kb = _create_knowledge_base(db, 1, visibility="public")
        resp = client.get(f"/api/knowledge-bases/{kb.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_kb_detail_private_as_creator(self, client: TestClient, db: Session):
        user = _create_user(db, "kb_creator", role=2)
        token = _login(client, "kb_creator")
        kb = _create_knowledge_base(db, user.id, visibility="private")
        resp = client.get(f"/api/knowledge-bases/{kb.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_kb_detail_private_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        kb = _create_knowledge_base(db, 1, visibility="private")
        resp = client.get(f"/api/knowledge-bases/{kb.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_get_kb_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge-bases/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_get_kb_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/knowledge-bases/1")
        assert resp.status_code == 401


class TestKnowledgeBaseCreate:
    """POST /api/knowledge-bases/ - Create knowledge base."""

    def test_create_kb_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {
            "name": "New KB",
            "description": "New knowledge base",
            "subject_id": 1,
            "visibility": "public",
        }
        resp = client.post("/api/knowledge-bases/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_create_kb_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        payload = {
            "name": "New KB",
            "description": "New knowledge base",
            "subject_id": 1,
            "visibility": "public",
        }
        resp = client.post("/api/knowledge-bases/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestKnowledgeBaseUpdate:
    """PUT /api/knowledge-bases/{kb_id} - Update knowledge base."""

    def test_update_kb_as_teacher(self, client: TestClient, db: Session):
        teacher = _create_user(db, "kb_teacher_up", role=2)
        token = _login(client, "kb_teacher_up")
        kb = _create_knowledge_base(db, teacher.id)
        payload = {"name": "Updated KB Name"}
        resp = client.put(f"/api/knowledge-bases/{kb.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_update_kb_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {"name": "Updated KB Name"}
        resp = client.put("/api/knowledge-bases/999999", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_update_kb_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        kb = _create_knowledge_base(db, 1)
        payload = {"name": "Updated KB Name"}
        resp = client.put(f"/api/knowledge-bases/{kb.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestKnowledgeBaseDelete:
    """DELETE /api/knowledge-bases/{kb_id} - Delete knowledge base."""

    def test_delete_kb_as_teacher(self, client: TestClient, db: Session):
        teacher = _create_user(db, "kb_teacher_del", role=2)
        token = _login(client, "kb_teacher_del")
        kb = _create_knowledge_base(db, teacher.id)
        resp = client.delete(f"/api/knowledge-bases/{kb.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_delete_kb_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        resp = client.delete("/api/knowledge-bases/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_delete_kb_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        kb = _create_knowledge_base(db, 1)
        resp = client.delete(f"/api/knowledge-bases/{kb.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestKnowledgeBaseEntries:
    """GET /api/knowledge-bases/{kb_id}/entries - List entries."""

    def test_list_entries(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        kb = _create_knowledge_base(db, 1)
        # Create an entry
        entry = KnowledgeEntry(
            knowledge_base_id=kb.id,
            title="Test Entry",
            content="Test content",
            order=0,
        )
        db.add(entry)
        db.commit()
        resp = client.get(f"/api/knowledge-bases/{kb.id}/entries", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_entries_kb_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge-bases/999999/entries", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_list_entries_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/knowledge-bases/1/entries")
        assert resp.status_code == 401


class TestKnowledgeBasePoints:
    """GET /api/knowledge-bases/{kb_id}/points - List knowledge points."""

    def test_list_points(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        kb = _create_knowledge_base(db, 1)
        # Create a knowledge point
        kp = KnowledgePoint(
            name="Test Point",
            knowledge_base_id=kb.id,
            status=1,
            created_by=1,
        )
        db.add(kp)
        db.commit()
        resp = client.get(f"/api/knowledge-bases/{kb.id}/points", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_points_kb_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/knowledge-bases/999999/points", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_list_points_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/knowledge-bases/1/points")
        assert resp.status_code == 401
