"""Integration tests for the Audit module.

Covers: pending list, detail view, approve/reject (single + batch), logs, statistics.
"""

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.question import AuditLog, Chapter, Question, QuestionOption, Subject
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
    _create_user(db, "audit_admin", role=1)
    return _login(client, "audit_admin")


def _teacher_token(client: TestClient, db: Session) -> str:
    _create_user(db, "audit_teacher", role=2)
    return _login(client, "audit_teacher")


def _student_token(client: TestClient, db: Session) -> str:
    _create_user(db, "audit_student", role=3)
    return _login(client, "audit_student")


def _create_subject_and_chapter(db: Session) -> tuple[Subject, Chapter]:
    """Create a subject and chapter for testing."""
    subject = db.query(Subject).filter(Subject.code == "AUDIT_TEST_SUBJ").first()
    if not subject:
        subject = Subject(name="Audit Test Subject", code="AUDIT_TEST_SUBJ", status=1)
        db.add(subject)
        db.commit()
        db.refresh(subject)
    chapter = db.query(Chapter).filter(Chapter.code == "AUDIT_TEST_CHAP").first()
    if not chapter:
        chapter = Chapter(subject_id=subject.id, name="Audit Test Chapter", code="AUDIT_TEST_CHAP", order=0, status=1)
        db.add(chapter)
        db.commit()
        db.refresh(chapter)
    return subject, chapter


def _create_question_for_audit(db: Session, user_id: int) -> Question:
    """Create a pending audit question."""
    subject, chapter = _create_subject_and_chapter(db)
    q = Question(
        chapter_id=chapter.id,
        subject_id=subject.id,
        question_type="single_choice",
        content="Audit test question: 2+2=?",
        difficulty=1,
        score=5.0,
        created_by=user_id,
        status=1,
        is_ai_generated=True,
        audit_status="pending",
        answer='{"correct": "B"}',
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    for label, text, is_correct in [("A", "3", False), ("B", "4", True), ("C", "5", False), ("D", "6", False)]:
        db.add(QuestionOption(question_id=q.id, option_label=label, option_content=text, is_correct=is_correct))
    db.commit()
    return q


class TestAuditPendingList:
    """GET /api/audit/pending - Get pending audit questions."""

    def test_list_pending_authenticated(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/audit/pending", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_pending_with_filters(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get(
            "/api/audit/pending?question_type=single_choice&difficulty=1",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_list_pending_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/audit/pending")
        assert resp.status_code == 401


class TestAuditDetail:
    """GET /api/audit/{question_id} - Get question for audit."""

    def test_get_audit_detail(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        q = _create_question_for_audit(db, 1)
        resp = client.get(f"/api/audit/{q.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_audit_detail_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/audit/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_get_audit_detail_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/audit/1")
        assert resp.status_code == 401


class TestAuditApprove:
    """POST /api/audit/{question_id}/approve - Approve a question."""

    def test_approve_question_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        q = _create_question_for_audit(db, 1)
        resp = client.post(f"/api/audit/{q.id}/approve", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_approve_question_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        q = _create_question_for_audit(db, 1)
        resp = client.post(f"/api/audit/{q.id}/approve", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_approve_question_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        resp = client.post("/api/audit/999999/approve", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_approve_already_audited(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        q = _create_question_for_audit(db, 1)
        # First approve
        client.post(f"/api/audit/{q.id}/approve", headers={"Authorization": f"Bearer {token}"})
        # Second approve should fail
        resp = client.post(f"/api/audit/{q.id}/approve", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400


class TestAuditReject:
    """POST /api/audit/{question_id}/reject - Reject a question."""

    def test_reject_question_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        q = _create_question_for_audit(db, 1)
        payload = {"reason": "Content is unclear"}
        resp = client.post(f"/api/audit/{q.id}/reject", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_reject_question_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        q = _create_question_for_audit(db, 1)
        payload = {"reason": "Content is unclear"}
        resp = client.post(f"/api/audit/{q.id}/reject", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_reject_question_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {"reason": "Content is unclear"}
        resp = client.post("/api/audit/999999/reject", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_reject_question_empty_reason(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        q = _create_question_for_audit(db, 1)
        payload = {"reason": ""}
        resp = client.post(f"/api/audit/{q.id}/reject", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 422


class TestAuditBatchApprove:
    """POST /api/audit/batch/approve - Batch approve questions."""

    def test_batch_approve_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        q1 = _create_question_for_audit(db, 1)
        q2 = _create_question_for_audit(db, 1)
        payload = {"ids": [q1.id, q2.id]}
        resp = client.post("/api/audit/batch/approve", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_batch_approve_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        q = _create_question_for_audit(db, 1)
        payload = {"ids": [q.id]}
        resp = client.post("/api/audit/batch/approve", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_batch_approve_empty_ids(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {"ids": []}
        resp = client.post("/api/audit/batch/approve", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 422

    def test_batch_approve_no_pending(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {"ids": [999999]}
        resp = client.post("/api/audit/batch/approve", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400


class TestAuditBatchReject:
    """POST /api/audit/batch/reject - Batch reject questions."""

    def test_batch_reject_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        q1 = _create_question_for_audit(db, 1)
        q2 = _create_question_for_audit(db, 1)
        payload = {"ids": [q1.id, q2.id], "reason": "Duplicate content"}
        resp = client.post("/api/audit/batch/reject", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_batch_reject_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        q = _create_question_for_audit(db, 1)
        payload = {"ids": [q.id], "reason": "Duplicate content"}
        resp = client.post("/api/audit/batch/reject", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_batch_reject_missing_reason(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        q = _create_question_for_audit(db, 1)
        payload = {"ids": [q.id]}
        resp = client.post("/api/audit/batch/reject", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400


class TestAuditLogs:
    """GET /api/audit/{question_id}/logs - Get audit logs for a question."""

    def test_get_audit_logs(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        q = _create_question_for_audit(db, 1)
        # Approve to create a log
        client.post(f"/api/audit/{q.id}/approve", headers={"Authorization": f"Bearer {token}"})
        resp = client.get(f"/api/audit/{q.id}/logs", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_audit_logs_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/audit/999999/logs", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200  # Returns empty list for non-existent question

    def test_get_audit_logs_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/audit/1/logs")
        assert resp.status_code == 401


class TestAuditStatistics:
    """GET /api/audit/statistics/summary - Get audit statistics."""

    def test_get_audit_statistics(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/audit/statistics/summary", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_audit_statistics_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/audit/statistics/summary")
        assert resp.status_code == 401
