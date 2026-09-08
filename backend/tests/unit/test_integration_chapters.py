"""Integration tests for the Chapters module.

Covers: chapter CRUD, list/detail operations, tree structure.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.question import Chapter, Subject
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
    _create_user(db, "chap_admin", role=1)
    return _login(client, "chap_admin")


def _teacher_token(client: TestClient, db: Session) -> str:
    _create_user(db, "chap_teacher", role=2)
    return _login(client, "chap_teacher")


def _student_token(client: TestClient, db: Session) -> str:
    _create_user(db, "chap_student", role=3)
    return _login(client, "chap_student")


def _create_subject(db: Session) -> Subject:
    """Create a test subject."""
    subject = db.query(Subject).filter(Subject.code == "CHAP_TEST_SUBJ").first()
    if not subject:
        subject = Subject(name="Chapter Test Subject", code="CHAP_TEST_SUBJ", status=1)
        db.add(subject)
        db.commit()
        db.refresh(subject)
    return subject


def _create_chapter(db: Session, subject_id: int) -> Chapter:
    """Create a test chapter."""
    chapter = Chapter(
        subject_id=subject_id,
        name="Test Chapter",
        code="TEST_CHAP",
        order=0,
        status=1,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


class TestChapterList:
    """GET /api/chapters/subjects/{subject_id}/chapters - List chapters."""

    def test_list_chapters_authenticated(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        subject = _create_subject(db)
        resp = client.get(f"/api/chapters/subjects/{subject.id}/chapters", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_chapters_as_tree(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        subject = _create_subject(db)
        resp = client.get(
            f"/api/chapters/subjects/{subject.id}/chapters?tree=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_list_chapters_unauthenticated(self, client: TestClient, db: Session):
        subject = _create_subject(db)
        resp = client.get(f"/api/chapters/subjects/{subject.id}/chapters")
        assert resp.status_code == 401


class TestChapterDetail:
    """GET /api/chapters/{chapter_id} - Get chapter details."""

    def test_get_chapter_detail(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        subject = _create_subject(db)
        chapter = _create_chapter(db, subject.id)
        resp = client.get(f"/api/chapters/{chapter.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_chapter_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/chapters/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_get_chapter_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/chapters/1")
        assert resp.status_code == 401


class TestChapterCreate:
    """POST /api/chapters/subjects/{subject_id}/chapters - Create chapter."""

    def test_create_chapter_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        subject = _create_subject(db)
        payload = {
            "name": "New Chapter",
            "code": "NEW_CHAP",
            "description": "New chapter description",
        }
        resp = client.post(
            f"/api/chapters/subjects/{subject.id}/chapters",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201

    def test_create_chapter_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        subject = _create_subject(db)
        payload = {
            "name": "New Chapter",
            "code": "NEW_CHAP2",
            "description": "New chapter description",
        }
        resp = client.post(
            f"/api/chapters/subjects/{subject.id}/chapters",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestChapterUpdate:
    """PUT /api/chapters/{chapter_id} - Update chapter."""

    def test_update_chapter_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        subject = _create_subject(db)
        chapter = _create_chapter(db, subject.id)
        payload = {"name": "Updated Chapter Name"}
        resp = client.put(f"/api/chapters/{chapter.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_update_chapter_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {"name": "Updated Chapter Name"}
        resp = client.put("/api/chapters/999999", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_update_chapter_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        subject = _create_subject(db)
        chapter = _create_chapter(db, subject.id)
        payload = {"name": "Updated Chapter Name"}
        resp = client.put(f"/api/chapters/{chapter.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestChapterDelete:
    """DELETE /api/chapters/{chapter_id} - Delete chapter (soft delete)."""

    def test_delete_chapter_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        subject = _create_subject(db)
        chapter = _create_chapter(db, subject.id)
        resp = client.delete(f"/api/chapters/{chapter.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 204

    def test_delete_chapter_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        resp = client.delete("/api/chapters/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_delete_chapter_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        subject = _create_subject(db)
        chapter = _create_chapter(db, subject.id)
        resp = client.delete(f"/api/chapters/{chapter.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
