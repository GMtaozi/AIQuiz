"""Integration tests for the Papers module.

Covers: paper CRUD, publish, export, analysis, similarity check.
"""

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.question import Chapter, ExamPaper, ExamPaperQuestion, Question, QuestionOption, Subject
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
    _create_user(db, "paper_admin", role=1)
    return _login(client, "paper_admin")


def _teacher_token(client: TestClient, db: Session) -> str:
    _create_user(db, "paper_teacher", role=2)
    return _login(client, "paper_teacher")


def _student_token(client: TestClient, db: Session) -> str:
    _create_user(db, "paper_student", role=3)
    return _login(client, "paper_student")


def _create_subject_and_chapter(db: Session) -> tuple[Subject, Chapter]:
    """Create a subject and chapter for testing."""
    subject = db.query(Subject).filter(Subject.code == "PAPER_TEST_SUBJ").first()
    if not subject:
        subject = Subject(name="Paper Test Subject", code="PAPER_TEST_SUBJ", status=1)
        db.add(subject)
        db.commit()
        db.refresh(subject)
    chapter = db.query(Chapter).filter(Chapter.code == "PAPER_TEST_CHAP").first()
    if not chapter:
        chapter = Chapter(subject_id=subject.id, name="Paper Test Chapter", code="PAPER_TEST_CHAP", order=0, status=1)
        db.add(chapter)
        db.commit()
        db.refresh(chapter)
    return subject, chapter


def _create_question(db: Session, chapter: Chapter, subject: Subject, user_id: int) -> Question:
    """Create a single choice question with options."""
    q = Question(
        chapter_id=chapter.id,
        subject_id=subject.id,
        question_type="single_choice",
        content="What is 1+1?",
        difficulty=1,
        score=5.0,
        created_by=user_id,
        status=1,
        answer='{"correct": "B"}',
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    for label, text, is_correct in [("A", "1", False), ("B", "2", True), ("C", "3", False), ("D", "4", False)]:
        db.add(QuestionOption(question_id=q.id, option_label=label, option_content=text, is_correct=is_correct))
    db.commit()
    return q


def _create_paper(db: Session, user_id: int, status: str = "draft") -> ExamPaper:
    """Create a draft paper with one question."""
    subject, chapter = _create_subject_and_chapter(db)
    q = _create_question(db, chapter, subject, user_id)
    paper = ExamPaper(
        title="Integration Test Paper",
        subject_id=subject.id,
        status=status,
        created_by=user_id,
        config={"paper_type": 1},
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    db.add(ExamPaperQuestion(exam_paper_id=paper.id, question_id=q.id, order=0, score=5.0))
    db.commit()
    return paper


class TestPaperList:
    """GET /api/papers/ - List papers."""

    def test_list_papers_authenticated(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/papers/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_papers_with_filters(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/papers/?status=0&keyword=Test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_papers_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/papers/")
        assert resp.status_code == 401


class TestPaperDetail:
    """GET /api/papers/{paper_id} - Get paper details."""

    def test_get_paper_detail_published(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        paper = _create_paper(db, 1, status="published")
        resp = client.get(f"/api/papers/{paper.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_paper_detail_draft_as_creator(self, client: TestClient, db: Session):
        user = _create_user(db, "paper_creator", role=2)
        token = _login(client, "paper_creator")
        paper = _create_paper(db, user.id, status="draft")
        resp = client.get(f"/api/papers/{paper.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_paper_detail_draft_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        paper = _create_paper(db, 1, status="draft")
        resp = client.get(f"/api/papers/{paper.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_get_paper_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/papers/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_get_paper_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/papers/1")
        assert resp.status_code == 401


class TestPaperCreate:
    """POST /api/papers/ - Create paper."""

    def test_create_fixed_paper_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        subject, chapter = _create_subject_and_chapter(db)
        q = _create_question(db, chapter, subject, 1)
        payload = {
            "paper_type": 1,
            "title": "New Fixed Paper",
            "subject_id": subject.id,
            "total_time": 120,
            "passing_score": 60.0,
            "description": "Test paper",
            "questions": [{"question_id": q.id, "order": 0, "score": 5.0}],
        }
        resp = client.post("/api/papers/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201

    def test_create_paper_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        subject, chapter = _create_subject_and_chapter(db)
        payload = {
            "paper_type": 1,
            "title": "New Paper",
            "subject_id": subject.id,
            "questions": [{"question_id": 1, "order": 0, "score": 5.0}],
        }
        resp = client.post("/api/papers/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_create_paper_subject_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {
            "paper_type": 1,
            "title": "New Paper",
            "subject_id": 999999,
            "questions": [{"question_id": 1, "order": 0, "score": 5.0}],
        }
        resp = client.post("/api/papers/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_create_paper_invalid_type(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        subject, chapter = _create_subject_and_chapter(db)
        payload = {
            "paper_type": 99,
            "title": "New Paper",
            "subject_id": subject.id,
            "questions": [{"question_id": 1, "order": 0, "score": 5.0}],
        }
        resp = client.post("/api/papers/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400


class TestPaperUpdate:
    """PUT /api/papers/{paper_id} - Update paper."""

    def test_update_paper_as_teacher(self, client: TestClient, db: Session):
        teacher = _create_user(db, "paper_teacher_up", role=2)
        token = _login(client, "paper_teacher_up")
        paper = _create_paper(db, teacher.id, status="draft")
        payload = {"title": "Updated Paper Title"}
        resp = client.put(f"/api/papers/{paper.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_update_published_paper_forbidden(self, client: TestClient, db: Session):
        teacher = _create_user(db, "paper_teacher_pub", role=2)
        token = _login(client, "paper_teacher_pub")
        paper = _create_paper(db, teacher.id, status="published")
        payload = {"title": "Updated Paper Title"}
        resp = client.put(f"/api/papers/{paper.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400

    def test_update_paper_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {"title": "Updated Paper Title"}
        resp = client.put("/api/papers/999999", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_update_paper_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        paper = _create_paper(db, 1, status="draft")
        payload = {"title": "Updated Paper Title"}
        resp = client.put(f"/api/papers/{paper.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestPaperDelete:
    """DELETE /api/papers/{paper_id} - Delete paper (soft delete)."""

    def test_delete_paper_as_teacher(self, client: TestClient, db: Session):
        teacher = _create_user(db, "paper_teacher_del", role=2)
        token = _login(client, "paper_teacher_del")
        paper = _create_paper(db, teacher.id, status="draft")
        resp = client.delete(f"/api/papers/{paper.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 204

    def test_delete_paper_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        resp = client.delete("/api/papers/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_delete_paper_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        paper = _create_paper(db, 1, status="draft")
        resp = client.delete(f"/api/papers/{paper.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestPaperPublish:
    """POST /api/papers/{paper_id}/publish - Publish paper."""

    def test_publish_paper_as_teacher(self, client: TestClient, db: Session):
        teacher = _create_user(db, "paper_teacher_pub2", role=2)
        token = _login(client, "paper_teacher_pub2")
        paper = _create_paper(db, teacher.id, status="draft")
        resp = client.post(f"/api/papers/{paper.id}/publish", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_publish_already_published(self, client: TestClient, db: Session):
        teacher = _create_user(db, "paper_teacher_pub3", role=2)
        token = _login(client, "paper_teacher_pub3")
        paper = _create_paper(db, teacher.id, status="published")
        resp = client.post(f"/api/papers/{paper.id}/publish", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400

    def test_publish_paper_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        resp = client.post("/api/papers/999999/publish", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_publish_paper_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        paper = _create_paper(db, 1, status="draft")
        resp = client.post(f"/api/papers/{paper.id}/publish", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestPaperAnalysis:
    """GET /api/papers/{paper_id}/analysis - Get paper analysis."""

    def test_get_paper_analysis(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        paper = _create_paper(db, 1, status="published")
        resp = client.get(f"/api/papers/{paper.id}/analysis", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_paper_analysis_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/papers/999999/analysis", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_get_paper_analysis_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/papers/1/analysis")
        assert resp.status_code == 401


class TestPaperSimilarityCheck:
    """POST /api/papers/{paper_id}/similarity-check - Check question similarity."""

    def test_similarity_check(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        paper = _create_paper(db, 1, status="published")
        payload = {"paper_id": paper.id, "threshold": 0.7}
        resp = client.post(f"/api/papers/{paper.id}/similarity-check", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_similarity_check_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        payload = {"paper_id": 999999, "threshold": 0.7}
        resp = client.post("/api/papers/999999/similarity-check", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_similarity_check_unauthenticated(self, client: TestClient, db: Session):
        payload = {"paper_id": 1, "threshold": 0.7}
        resp = client.post("/api/papers/1/similarity-check", json=payload)
        assert resp.status_code == 401
