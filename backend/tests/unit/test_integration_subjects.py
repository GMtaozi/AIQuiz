"""Integration tests for the Subjects module.

Covers: subject CRUD, list/detail operations.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.question import Subject
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
    _create_user(db, "subj_admin", role=1)
    return _login(client, "subj_admin")


def _teacher_token(client: TestClient, db: Session) -> str:
    _create_user(db, "subj_teacher", role=2)
    return _login(client, "subj_teacher")


def _student_token(client: TestClient, db: Session) -> str:
    _create_user(db, "subj_student", role=3)
    return _login(client, "subj_student")


def _create_subject(db: Session) -> Subject:
    """Create a test subject."""
    subject = db.query(Subject).filter(Subject.code == "TEST_SUBJ").first()
    if not subject:
        subject = Subject(name="Test Subject", code="TEST_SUBJ", status=1)
        db.add(subject)
        db.commit()
        db.refresh(subject)
    return subject


class TestSubjectList:
    """GET /api/subjects/ - List subjects."""

    def test_list_subjects_authenticated(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/subjects/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_subjects_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/subjects/")
        assert resp.status_code == 401


class TestSubjectDetail:
    """GET /api/subjects/{subject_id} - Get subject details."""

    def test_get_subject_detail(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        subject = _create_subject(db)
        resp = client.get(f"/api/subjects/{subject.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_subject_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/subjects/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_get_subject_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/subjects/1")
        assert resp.status_code == 401


class TestSubjectCreate:
    """POST /api/subjects/ - Create subject."""

    def test_create_subject_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {
            "name": "New Subject",
            "code": "NEW_SUBJ",
            "description": "New subject description",
        }
        resp = client.post("/api/subjects/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201

    def test_create_subject_duplicate_code(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        _create_subject(db)  # Creates subject with code "TEST_SUBJ"
        payload = {
            "name": "Duplicate Subject",
            "code": "TEST_SUBJ",
            "description": "Duplicate subject",
        }
        resp = client.post("/api/subjects/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400

    def test_create_subject_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        payload = {
            "name": "New Subject",
            "code": "NEW_SUBJ2",
            "description": "New subject description",
        }
        resp = client.post("/api/subjects/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestSubjectUpdate:
    """PUT /api/subjects/{subject_id} - Update subject."""

    def test_update_subject_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        subject = _create_subject(db)
        payload = {"name": "Updated Subject Name"}
        resp = client.put(f"/api/subjects/{subject.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_update_subject_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {"name": "Updated Subject Name"}
        resp = client.put("/api/subjects/999999", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_update_subject_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        subject = _create_subject(db)
        payload = {"name": "Updated Subject Name"}
        resp = client.put(f"/api/subjects/{subject.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestSubjectDelete:
    """DELETE /api/subjects/{subject_id} - Delete subject (soft delete)."""

    def test_delete_subject_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        subject = _create_subject(db)
        resp = client.delete(f"/api/subjects/{subject.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 204

    def test_delete_subject_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        resp = client.delete("/api/subjects/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_delete_subject_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        subject = _create_subject(db)
        resp = client.delete(f"/api/subjects/{subject.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
