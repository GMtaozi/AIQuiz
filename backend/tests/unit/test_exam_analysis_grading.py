"""Unit tests for exam analysis and subjective grading features.

Covers:
- GET /api/exams/{exam_id}/analysis — exam analysis report
- POST /api/exams/{exam_id}/grade-subjective — subjective question grading
"""

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.question import (
    Chapter,
    ExamPaper,
    ExamPaperQuestion,
    ExamRecord,
    Question,
    QuestionOption,
    Subject,
    UserAnswer,
)
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
    _create_user(db, "analysis_admin", role=1)
    return _login(client, "analysis_admin")


def _teacher_token(client: TestClient, db: Session) -> str:
    _create_user(db, "analysis_teacher", role=2)
    return _login(client, "analysis_teacher")


def _student_token(client: TestClient, db: Session) -> str:
    _create_user(db, "analysis_student", role=3)
    return _login(client, "analysis_student")


def _create_subject_and_chapter(db: Session) -> tuple[Subject, Chapter]:
    """Create a subject and chapter for testing."""
    subject = db.query(Subject).filter(Subject.code == "ANALYSIS_TEST_SUBJ").first()
    if not subject:
        subject = Subject(name="Analysis Test Subject", code="ANALYSIS_TEST_SUBJ", status=1)
        db.add(subject)
        db.commit()
        db.refresh(subject)
    chapter = db.query(Chapter).filter(Chapter.code == "ANALYSIS_TEST_CHAP").first()
    if not chapter:
        chapter = Chapter(subject_id=subject.id, name="Analysis Test Chapter", code="ANALYSIS_TEST_CHAP", order=0, status=1)
        db.add(chapter)
        db.commit()
        db.refresh(chapter)
    return subject, chapter


def _create_question(
    db: Session,
    chapter: Chapter,
    subject: Subject,
    user_id: int,
    question_type: str = "single_choice",
    difficulty: int = 1,
    score: float = 5.0,
    meta: dict | None = None,
) -> Question:
    """Create a question with options."""
    q = Question(
        chapter_id=chapter.id,
        subject_id=subject.id,
        question_type=question_type,
        content=f"Test {question_type} question",
        difficulty=difficulty,
        score=score,
        created_by=user_id,
        status=1,
        meta=meta,
    )
    db.add(q)
    db.commit()
    db.refresh(q)

    if question_type in ("single_choice", "multiple_choice", "true_false"):
        for label, text, is_correct in [("A", "Option A", True), ("B", "Option B", False), ("C", "Option C", False)]:
            db.add(QuestionOption(question_id=q.id, option_label=label, option_content=text, is_correct=is_correct))
        db.commit()
    return q


def _create_paper_with_questions(
    db: Session,
    user_id: int,
    include_subjective: bool = False,
    meta_kp_ids: list[int] | None = None,
) -> ExamPaper:
    """Create a published exam paper with questions."""
    subject, chapter = _create_subject_and_chapter(db)
    now = datetime.utcnow()

    # Create objective question
    obj_q = _create_question(
        db, chapter, subject, user_id,
        question_type="single_choice", difficulty=2, score=5.0,
        meta={"knowledge_point_ids": meta_kp_ids or [1, 2]},
    )

    paper = ExamPaper(
        title="Analysis Test Paper",
        subject_id=subject.id,
        status="published",
        created_by=user_id,
        total_score=100.0,
        passing_score=60.0,
        config={
            "exam_title": "Analysis Test Paper",
            "exam_status": "published",
            "student_ids": [user_id],
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=2)).isoformat(),
        },
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    db.add(ExamPaperQuestion(exam_paper_id=paper.id, question_id=obj_q.id, order=0, score=5.0))

    if include_subjective:
        subj_q = _create_question(
            db, chapter, subject, user_id,
            question_type="essay", difficulty=3, score=15.0,
            meta={"knowledge_point_ids": meta_kp_ids or [1, 2]},
        )
        db.add(ExamPaperQuestion(exam_paper_id=paper.id, question_id=subj_q.id, order=1, score=15.0))

    db.commit()
    return paper


def _create_exam_record(
    db: Session,
    paper_id: int,
    student_id: int,
    status: str = "graded",
    score: float | None = None,
) -> ExamRecord:
    """Create an exam record."""
    record = ExamRecord(
        exam_paper_id=paper_id,
        user_id=student_id,
        status=status,
        started_at=datetime.utcnow() - timedelta(hours=1),
        submitted_at=datetime.utcnow() - timedelta(minutes=30),
        score=score,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _create_user_answer(
    db: Session,
    record_id: int,
    question_id: int,
    user_id: int,
    answer_content: str = "A",
    is_correct: bool | None = None,
    score: float | None = None,
) -> UserAnswer:
    """Create a user answer."""
    answer = UserAnswer(
        exam_record_id=record_id,
        question_id=question_id,
        user_id=user_id,
        answer_content=answer_content,
        is_correct=is_correct,
        score=score,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


# ============ Exam Analysis Tests ============


class TestExamAnalysis:
    """GET /api/exams/{exam_id}/analysis - Exam analysis report."""

    def test_analysis_as_teacher(self, client: TestClient, db: Session):
        """Teacher can view exam analysis."""
        teacher = _create_user(db, "analysis_teacher_1", role=2)
        token = _login(client, "analysis_teacher_1")
        paper = _create_paper_with_questions(db, teacher.id, meta_kp_ids=[1, 2])

        # Create student records
        student1 = _create_user(db, "analysis_student_1", role=3)
        student2 = _create_user(db, "analysis_student_2", role=3)
        record1 = _create_exam_record(db, paper.id, student1.id, status="graded", score=85.0)
        record2 = _create_exam_record(db, paper.id, student2.id, status="graded", score=75.0)

        # Create user answers
        pq = db.query(ExamPaperQuestion).filter(ExamPaperQuestion.exam_paper_id == paper.id).first()
        _create_user_answer(db, record1.id, pq.question_id, student1.id, "A", True, 5.0)
        _create_user_answer(db, record2.id, pq.question_id, student2.id, "A", True, 5.0)

        resp = client.get(f"/api/exams/{paper.id}/analysis", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["exam_id"] == paper.id
        assert data["total_students"] >= 2
        assert data["submitted_count"] >= 2
        assert data["graded_count"] >= 2
        assert data["average_score"] == 80.0
        assert data["max_score"] == 85.0
        assert data["min_score"] == 75.0
        assert data["pass_rate"] == 100.0
        assert len(data["question_stats"]) >= 1
        assert data["question_stats"][0]["correct_rate"] == 100.0

    def test_analysis_as_admin(self, client: TestClient, db: Session):
        """Admin can view exam analysis."""
        admin = _create_user(db, "analysis_admin_1", role=1)
        token = _login(client, "analysis_admin_1")
        paper = _create_paper_with_questions(db, admin.id)

        resp = client.get(f"/api/exams/{paper.id}/analysis", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["exam_id"] == paper.id

    def test_analysis_as_student_forbidden(self, client: TestClient, db: Session):
        """Student cannot view exam analysis."""
        teacher = _create_user(db, "analysis_teacher_2", role=2)
        student = _create_user(db, "analysis_student_3", role=3)
        token = _login(client, "analysis_student_3")
        paper = _create_paper_with_questions(db, teacher.id)

        resp = client.get(f"/api/exams/{paper.id}/analysis", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_analysis_exam_not_found(self, client: TestClient, db: Session):
        """Returns 404 for non-existent exam."""
        token = _teacher_token(client, db)
        resp = client.get("/api/exams/999999/analysis", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404

    def test_analysis_unauthenticated(self, client: TestClient, db: Session):
        """Returns 401 for unauthenticated request."""
        teacher = _create_user(db, "analysis_teacher_3", role=2)
        paper = _create_paper_with_questions(db, teacher.id)
        resp = client.get(f"/api/exams/{paper.id}/analysis")
        assert resp.status_code == 401

    def test_analysis_no_records(self, client: TestClient, db: Session):
        """Analysis with no submitted records returns zeros."""
        teacher = _create_user(db, "analysis_teacher_4", role=2)
        token = _login(client, "analysis_teacher_4")
        paper = _create_paper_with_questions(db, teacher.id)

        resp = client.get(f"/api/exams/{paper.id}/analysis", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["submitted_count"] == 0
        assert data["graded_count"] == 0
        assert data["average_score"] == 0.0
        assert data["pass_rate"] == 0.0

    def test_analysis_score_distribution(self, client: TestClient, db: Session):
        """Score distribution is correctly calculated."""
        teacher = _create_user(db, "analysis_teacher_5", role=2)
        token = _login(client, "analysis_teacher_5")
        paper = _create_paper_with_questions(db, teacher.id)

        # Create students with different scores
        for i, score in enumerate([95.0, 85.0, 75.0, 65.0, 55.0]):
            student = _create_user(db, f"analysis_dist_{i}", role=3)
            _create_exam_record(db, paper.id, student.id, status="graded", score=score)

        resp = client.get(f"/api/exams/{paper.id}/analysis", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        dist = data["score_distribution"]
        assert dist["range_90_100"] == 1
        assert dist["range_80_89"] == 1
        assert dist["range_70_79"] == 1
        assert dist["range_60_69"] == 1
        assert dist["range_0_59"] == 1

    def test_analysis_knowledge_point_stats(self, client: TestClient, db: Session):
        """Knowledge point analysis is included."""
        teacher = _create_user(db, "analysis_teacher_6", role=2)
        token = _login(client, "analysis_teacher_6")
        paper = _create_paper_with_questions(db, teacher.id, meta_kp_ids=[10, 20])

        student = _create_user(db, "analysis_kp_student", role=3)
        record = _create_exam_record(db, paper.id, student.id, status="graded", score=80.0)

        pq = db.query(ExamPaperQuestion).filter(ExamPaperQuestion.exam_paper_id == paper.id).first()
        _create_user_answer(db, record.id, pq.question_id, student.id, "A", True, 5.0)

        resp = client.get(f"/api/exams/{paper.id}/analysis", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["knowledge_point_stats"]) >= 1


# ============ Subjective Grading Tests ============


class TestSubjectiveGrading:
    """POST /api/exams/{exam_id}/grade-subjective - Grade subjective questions."""

    def test_grade_subjective_as_teacher(self, client: TestClient, db: Session):
        """Teacher can grade subjective questions."""
        teacher = _create_user(db, "grade_teacher_1", role=2)
        token = _login(client, "grade_teacher_1")
        paper = _create_paper_with_questions(db, teacher.id, include_subjective=True)

        # Get the subjective question
        subj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper.id, Question.question_type == "essay")
            .first()
        )
        assert subj_pq is not None

        # Create student and record
        student = _create_user(db, "grade_student_1", role=3)
        record = _create_exam_record(db, paper.id, student.id, status="submitted")
        answer = _create_user_answer(db, record.id, subj_pq.question_id, student.id, "My essay answer")

        payload = {
            "exam_record_id": record.id,
            "question_id": subj_pq.question_id,
            "score": 12.0,
            "feedback": "Good answer, but needs more detail.",
        }
        resp = client.post(
            f"/api/exams/{paper.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["exam_record_id"] == record.id
        assert data["question_id"] == subj_pq.question_id
        assert data["score"] == 12.0
        assert data["feedback"] == "Good answer, but needs more detail."
        assert data["graded_by"] == teacher.id
        assert data["record_status"] == "graded"
        assert data["all_subjective_graded"] is True

    def test_grade_subjective_as_admin(self, client: TestClient, db: Session):
        """Admin can grade subjective questions."""
        admin = _create_user(db, "grade_admin_1", role=1)
        token = _login(client, "grade_admin_1")
        paper = _create_paper_with_questions(db, admin.id, include_subjective=True)

        subj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper.id, Question.question_type == "essay")
            .first()
        )

        student = _create_user(db, "grade_student_2", role=3)
        record = _create_exam_record(db, paper.id, student.id, status="submitted")
        _create_user_answer(db, record.id, subj_pq.question_id, student.id, "Answer")

        payload = {
            "exam_record_id": record.id,
            "question_id": subj_pq.question_id,
            "score": 10.0,
        }
        resp = client.post(
            f"/api/exams/{paper.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_grade_subjective_as_student_forbidden(self, client: TestClient, db: Session):
        """Student cannot grade subjective questions."""
        teacher = _create_user(db, "grade_teacher_2", role=2)
        student = _create_user(db, "grade_student_3", role=3)
        token = _login(client, "grade_student_3")
        paper = _create_paper_with_questions(db, teacher.id, include_subjective=True)

        subj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper.id, Question.question_type == "essay")
            .first()
        )

        payload = {
            "exam_record_id": 1,
            "question_id": subj_pq.question_id,
            "score": 10.0,
        }
        resp = client.post(
            f"/api/exams/{paper.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_grade_subjective_exam_not_found(self, client: TestClient, db: Session):
        """Returns 404 for non-existent exam record."""
        token = _teacher_token(client, db)
        payload = {
            "exam_record_id": 999999,
            "question_id": 1,
            "score": 10.0,
        }
        resp = client.post(
            "/api/exams/999999/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_grade_subjective_record_not_found(self, client: TestClient, db: Session):
        """Returns 404 for non-existent exam record."""
        teacher = _create_user(db, "grade_teacher_3", role=2)
        token = _login(client, "grade_teacher_3")
        paper = _create_paper_with_questions(db, teacher.id, include_subjective=True)

        subj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper.id, Question.question_type == "essay")
            .first()
        )

        payload = {
            "exam_record_id": 999999,
            "question_id": subj_pq.question_id,
            "score": 10.0,
        }
        resp = client.post(
            f"/api/exams/{paper.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_grade_subjective_question_not_in_paper(self, client: TestClient, db: Session):
        """Returns 404 when question is not in the paper."""
        teacher = _create_user(db, "grade_teacher_4", role=2)
        token = _login(client, "grade_teacher_4")
        paper = _create_paper_with_questions(db, teacher.id, include_subjective=True)

        student = _create_user(db, "grade_student_4", role=3)
        record = _create_exam_record(db, paper.id, student.id, status="submitted")

        payload = {
            "exam_record_id": record.id,
            "question_id": 999999,
            "score": 10.0,
        }
        resp = client.post(
            f"/api/exams/{paper.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_grade_subjective_objective_question_rejected(self, client: TestClient, db: Session):
        """Cannot grade objective questions via this endpoint."""
        teacher = _create_user(db, "grade_teacher_5", role=2)
        token = _login(client, "grade_teacher_5")
        paper = _create_paper_with_questions(db, teacher.id)

        obj_pq = db.query(ExamPaperQuestion).filter(ExamPaperQuestion.exam_paper_id == paper.id).first()

        student = _create_user(db, "grade_student_5", role=3)
        record = _create_exam_record(db, paper.id, student.id, status="submitted")
        _create_user_answer(db, record.id, obj_pq.question_id, student.id, "A")

        payload = {
            "exam_record_id": record.id,
            "question_id": obj_pq.question_id,
            "score": 5.0,
        }
        resp = client.post(
            f"/api/exams/{paper.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_grade_subjective_score_exceeds_full_score(self, client: TestClient, db: Session):
        """Score cannot exceed the question's full score."""
        teacher = _create_user(db, "grade_teacher_6", role=2)
        token = _login(client, "grade_teacher_6")
        paper = _create_paper_with_questions(db, teacher.id, include_subjective=True)

        subj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper.id, Question.question_type == "essay")
            .first()
        )

        student = _create_user(db, "grade_student_6", role=3)
        record = _create_exam_record(db, paper.id, student.id, status="submitted")
        _create_user_answer(db, record.id, subj_pq.question_id, student.id, "Answer")

        payload = {
            "exam_record_id": record.id,
            "question_id": subj_pq.question_id,
            "score": 999.0,  # Exceeds full score
        }
        resp = client.post(
            f"/api/exams/{paper.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_grade_subjective_answer_not_found(self, client: TestClient, db: Session):
        """Returns 404 when no answer record exists."""
        teacher = _create_user(db, "grade_teacher_7", role=2)
        token = _login(client, "grade_teacher_7")
        paper = _create_paper_with_questions(db, teacher.id, include_subjective=True)

        subj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper.id, Question.question_type == "essay")
            .first()
        )

        student = _create_user(db, "grade_student_7", role=3)
        record = _create_exam_record(db, paper.id, student.id, status="submitted")
        # No answer created

        payload = {
            "exam_record_id": record.id,
            "question_id": subj_pq.question_id,
            "score": 10.0,
        }
        resp = client.post(
            f"/api/exams/{paper.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    def test_grade_subjective_record_mismatch(self, client: TestClient, db: Session):
        """Returns 400 when exam_record does not belong to the exam."""
        teacher = _create_user(db, "grade_teacher_8", role=2)
        token = _login(client, "grade_teacher_8")
        paper1 = _create_paper_with_questions(db, teacher.id, include_subjective=True)
        paper2 = _create_paper_with_questions(db, teacher.id, include_subjective=True)

        subj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper1.id, Question.question_type == "essay")
            .first()
        )

        student = _create_user(db, "grade_student_8", role=3)
        record2 = _create_exam_record(db, paper2.id, student.id, status="submitted")

        payload = {
            "exam_record_id": record2.id,
            "question_id": subj_pq.question_id,
            "score": 10.0,
        }
        resp = client.post(
            f"/api/exams/{paper1.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400

    def test_grade_subjective_updates_total_score(self, client: TestClient, db: Session):
        """Grading subjective question updates the record's total score."""
        teacher = _create_user(db, "grade_teacher_9", role=2)
        token = _login(client, "grade_teacher_9")
        paper = _create_paper_with_questions(db, teacher.id, include_subjective=True)

        obj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper.id, Question.question_type == "single_choice")
            .first()
        )
        subj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper.id, Question.question_type == "essay")
            .first()
        )

        student = _create_user(db, "grade_student_9", role=3)
        record = _create_exam_record(db, paper.id, student.id, status="submitted")
        _create_user_answer(db, record.id, obj_pq.question_id, student.id, "A", True, 5.0)
        _create_user_answer(db, record.id, subj_pq.question_id, student.id, "Essay answer")

        payload = {
            "exam_record_id": record.id,
            "question_id": subj_pq.question_id,
            "score": 12.0,
        }
        resp = client.post(
            f"/api/exams/{paper.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["record_total_score"] == 17.0  # 5.0 + 12.0

    def test_grade_subjective_unauthenticated(self, client: TestClient, db: Session):
        """Returns 401 for unauthenticated request."""
        teacher = _create_user(db, "grade_teacher_10", role=2)
        paper = _create_paper_with_questions(db, teacher.id, include_subjective=True)

        subj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper.id, Question.question_type == "essay")
            .first()
        )

        payload = {
            "exam_record_id": 1,
            "question_id": subj_pq.question_id,
            "score": 10.0,
        }
        resp = client.post(f"/api/exams/{paper.id}/grade-subjective", json=payload)
        assert resp.status_code == 401

    def test_grade_subjective_negative_score_rejected(self, client: TestClient, db: Session):
        """Negative score is rejected by schema validation."""
        teacher = _create_user(db, "grade_teacher_11", role=2)
        token = _login(client, "grade_teacher_11")
        paper = _create_paper_with_questions(db, teacher.id, include_subjective=True)

        subj_pq = (
            db.query(ExamPaperQuestion)
            .join(Question, ExamPaperQuestion.question_id == Question.id)
            .filter(ExamPaperQuestion.exam_paper_id == paper.id, Question.question_type == "essay")
            .first()
        )

        student = _create_user(db, "grade_student_11", role=3)
        record = _create_exam_record(db, paper.id, student.id, status="submitted")
        _create_user_answer(db, record.id, subj_pq.question_id, student.id, "Answer")

        payload = {
            "exam_record_id": record.id,
            "question_id": subj_pq.question_id,
            "score": -5.0,
        }
        resp = client.post(
            f"/api/exams/{paper.id}/grade-subjective",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422  # Validation error
