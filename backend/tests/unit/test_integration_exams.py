"""Integration tests for the Exams module.

Covers: exam CRUD, start/submit/grade flow, access control, 404/403 scenarios.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.question import Chapter, ExamPaper, ExamPaperQuestion, ExamRecord, Question, QuestionOption, Subject
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
    _create_user(db, "exam_admin", role=1)
    return _login(client, "exam_admin")


def _teacher_token(client: TestClient, db: Session) -> str:
    _create_user(db, "exam_teacher", role=2)
    return _login(client, "exam_teacher")


def _student_token(client: TestClient, db: Session) -> str:
    _create_user(db, "exam_student", role=3)
    return _login(client, "exam_student")


def _create_subject_and_chapter(db: Session) -> tuple[Subject, Chapter]:
    """Create a subject and chapter for testing."""
    subject = db.query(Subject).filter(Subject.code == "EXAM_TEST_SUBJ").first()
    if not subject:
        subject = Subject(name="Exam Test Subject", code="EXAM_TEST_SUBJ", status=1)
        db.add(subject)
        db.commit()
        db.refresh(subject)
    chapter = db.query(Chapter).filter(Chapter.code == "EXAM_TEST_CHAP").first()
    if not chapter:
        chapter = Chapter(subject_id=subject.id, name="Exam Test Chapter", code="EXAM_TEST_CHAP", order=0, status=1)
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


def _create_paper_with_questions(db: Session, user_id: int) -> ExamPaper:
    """Create a published exam paper with one question."""
    subject, chapter = _create_subject_and_chapter(db)
    q = _create_question(db, chapter, subject, user_id)
    now = datetime.utcnow()
    paper = ExamPaper(
        title="Integration Test Paper",
        subject_id=subject.id,
        status="published",
        created_by=user_id,
        config={
            "exam_title": "Integration Test Paper",
            "exam_status": "published",
            "student_ids": [user_id],
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
        },
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    db.add(ExamPaperQuestion(exam_paper_id=paper.id, question_id=q.id, order=0, score=3.0))
    db.commit()
    return paper


class TestExamList:
    """GET /api/exams/ - List exams."""

    def test_list_exams_authenticated(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/exams/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_exams_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/exams/")
        assert resp.status_code == 401

    def test_list_exams_with_subject_filter(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/exams/?subject_id=1", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestExamDetail:
    """GET /api/exams/{exam_id} - Get exam details."""

    def test_get_exam_detail(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        paper = _create_paper_with_questions(db, 1)
        resp = client.get(f"/api/exams/{paper.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_exam_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/exams/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_get_exam_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/exams/1")
        assert resp.status_code == 401


class TestExamCreate:
    """POST /api/exams/ - Create exam."""

    def test_create_exam_as_teacher(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        paper = _create_paper_with_questions(db, 1)
        student = _create_user(db, "exam_student_for_create", role=3)
        payload = {
            "exam_paper_id": paper.id,
            "subject_id": paper.subject_id,
            "title": "New Exam",
            "duration": 60,
            "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            "student_ids": [student.id],
        }
        resp = client.post("/api/exams/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201

    def test_create_exam_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        paper = _create_paper_with_questions(db, 1)
        payload = {
            "exam_paper_id": paper.id,
            "subject_id": paper.subject_id,
            "title": "New Exam",
            "duration": 60,
            "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            "student_ids": [],
        }
        resp = client.post("/api/exams/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_create_exam_paper_not_found(self, client: TestClient, db: Session):
        token = _teacher_token(client, db)
        payload = {
            "exam_paper_id": 999999,
            "subject_id": 1,
            "title": "New Exam",
            "duration": 60,
            "start_time": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "end_time": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            "student_ids": [],
        }
        resp = client.post("/api/exams/", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404


class TestExamUpdate:
    """PUT /api/exams/{exam_id} - Update exam."""

    def test_update_exam_as_creator(self, client: TestClient, db: Session):
        user = _create_user(db, "exam_creator", role=2)
        token = _login(client, "exam_creator")
        paper = _create_paper_with_questions(db, user.id)
        payload = {"title": "Updated Exam Title"}
        resp = client.put(f"/api/exams/{paper.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_update_exam_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        payload = {"title": "Updated Exam Title"}
        resp = client.put("/api/exams/999999", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_update_exam_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        paper = _create_paper_with_questions(db, 1)
        payload = {"title": "Updated Exam Title"}
        resp = client.put(f"/api/exams/{paper.id}", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestExamDelete:
    """DELETE /api/exams/{exam_id} - Delete exam."""

    def test_delete_exam_as_admin(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        paper = _create_paper_with_questions(db, 1)
        resp = client.delete(f"/api/exams/{paper.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 204

    def test_delete_exam_not_found(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.delete("/api/exams/999999", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_delete_exam_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        paper = _create_paper_with_questions(db, 1)
        resp = client.delete(f"/api/exams/{paper.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestExamStart:
    """POST /api/exams/{exam_id}/start - Start exam."""

    def test_start_exam_as_student(self, client: TestClient, db: Session):
        student = _create_user(db, "exam_starter", role=3)
        token = _login(client, "exam_starter")
        paper = _create_paper_with_questions(db, student.id)
        # Ensure student is in the exam's student_ids
        paper.config["student_ids"] = [student.id]
        db.commit()
        resp = client.post(f"/api/exams/{paper.id}/start", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (200, 201)

    def test_start_exam_not_in_list(self, client: TestClient, db: Session):
        student = _create_user(db, "exam_not_in_list", role=3)
        token = _login(client, "exam_not_in_list")
        paper = _create_paper_with_questions(db, 1)
        paper.config["student_ids"] = [999]  # Student not in list
        db.commit()
        resp = client.post(f"/api/exams/{paper.id}/start", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_start_exam_not_found(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        resp = client.post("/api/exams/999999/start", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404


class TestExamSubmit:
    """POST /api/exams/{exam_id}/submit - Submit exam answers."""

    def test_submit_exam_success(self, client: TestClient, db: Session):
        student = _create_user(db, "exam_submitter", role=3)
        token = _login(client, "exam_submitter")
        paper = _create_paper_with_questions(db, student.id)
        paper.config["student_ids"] = [student.id]
        db.commit()

        # Start exam
        start_resp = client.post(f"/api/exams/{paper.id}/start", headers={"Authorization": f"Bearer {token}"})
        assert start_resp.status_code in (200, 201)
        record_id = start_resp.json()["data"][0]["id"]

        # Get questions
        questions_resp = client.get(f"/api/exams/{paper.id}/questions", headers={"Authorization": f"Bearer {token}"})
        assert questions_resp.status_code == 200
        questions = questions_resp.json()["data"]

        # Submit answers
        answers = [{"question_id": q["question_id"], "answer_content": "B"} for q in questions]
        submit_resp = client.post(
            f"/api/exams/{paper.id}/submit?exam_record_id={record_id}",
            json=answers,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert submit_resp.status_code == 200
        data = submit_resp.json()["data"]
        assert data["status"] == "graded"
        assert float(data["score"]) == 3.0

    def test_submit_exam_wrong_answer(self, client: TestClient, db: Session):
        student = _create_user(db, "exam_wrong_answer", role=3)
        token = _login(client, "exam_wrong_answer")
        paper = _create_paper_with_questions(db, student.id)
        paper.config["student_ids"] = [student.id]
        db.commit()

        start_resp = client.post(f"/api/exams/{paper.id}/start", headers={"Authorization": f"Bearer {token}"})
        record_id = start_resp.json()["data"][0]["id"]
        questions = client.get(f"/api/exams/{paper.id}/questions", headers={"Authorization": f"Bearer {token}"}).json()["data"]

        answers = [{"question_id": q["question_id"], "answer_content": "A"} for q in questions]
        submit_resp = client.post(
            f"/api/exams/{paper.id}/submit?exam_record_id={record_id}",
            json=answers,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert submit_resp.status_code == 200
        data = submit_resp.json()["data"]
        assert data["status"] == "graded"
        assert float(data["score"]) == 0.0

    def test_submit_exam_record_not_found(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        paper = _create_paper_with_questions(db, 1)
        answers = [{"question_id": 1, "answer_content": "B"}]
        resp = client.post(
            f"/api/exams/{paper.id}/submit?exam_record_id=999999",
            json=answers,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestExamGrade:
    """POST /api/exams/{exam_id}/grade - Grade exam (teacher only)."""

    def test_grade_exam_as_teacher(self, client: TestClient, db: Session):
        teacher = _create_user(db, "exam_grader", role=2)
        token = _login(client, "exam_grader")
        paper = _create_paper_with_questions(db, teacher.id)

        # Create an exam record
        record = ExamRecord(
            exam_paper_id=paper.id,
            user_id=teacher.id,
            status="submitted",
            started_at=datetime.utcnow(),
            submitted_at=datetime.utcnow(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        payload = {"exam_record_id": record.id}
        resp = client.post(f"/api/exams/{paper.id}/grade", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_grade_exam_as_student_forbidden(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        paper = _create_paper_with_questions(db, 1)
        payload = {"exam_record_id": 1}
        resp = client.post(f"/api/exams/{paper.id}/grade", json=payload, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestExamQuestions:
    """GET /api/exams/{exam_id}/questions - Get exam questions for student."""

    def test_get_questions_authenticated(self, client: TestClient, db: Session):
        student = _create_user(db, "exam_q_viewer", role=3)
        token = _login(client, "exam_q_viewer")
        paper = _create_paper_with_questions(db, student.id)
        paper.config["student_ids"] = [student.id]
        db.commit()
        resp = client.get(f"/api/exams/{paper.id}/questions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_questions_not_in_list(self, client: TestClient, db: Session):
        student = _create_user(db, "exam_q_not_list", role=3)
        token = _login(client, "exam_q_not_list")
        paper = _create_paper_with_questions(db, 1)
        paper.config["student_ids"] = [999]
        db.commit()
        resp = client.get(f"/api/exams/{paper.id}/questions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_get_questions_not_found(self, client: TestClient, db: Session):
        token = _student_token(client, db)
        resp = client.get("/api/exams/999999/questions", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404
