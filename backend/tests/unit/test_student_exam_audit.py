"""学生考试链路审计修复回归：交卷自动判分 + 卷面分 + 时间窗。"""
import uuid

import pytest

from app.models.question import (
    ExamPaper,
    ExamPaperQuestion,
    Question,
    QuestionOption,
)
from app.models.user import User
from app.services.auth import AuthService


@pytest.fixture()
def student_with_exam(client, db):
    """建学生 + 单选试卷（卷面分 3.0，题库默认分 5.0）并发布考试。"""
    from app.models.question import Chapter, Subject

    suffix = uuid.uuid4().hex[:6]
    student = User(
        username=f"audit_stu_{suffix}", email=f"audit_stu_{suffix}@test.com", role=3, status=1,
        hashed_password=AuthService.get_password_hash("Str0ng!Pass"),
        menu_permissions=[],
    )
    db.add(student)

    subject = db.query(Subject).first() or Subject(name="审计科目", code="AUDIT", status=1)
    db.add(subject)
    db.flush()
    chapter = Chapter(subject_id=subject.id, name="审计章节", code=f"AUD-{suffix}", order=0)
    db.add(chapter)
    db.flush()

    q = Question(
        chapter_id=chapter.id, question_type="single_choice",
        content="审计测试题：1+1=?", difficulty=1, subject_id=subject.id,
        created_by=student.id, status=1, score=5.0,  # 题库默认分 5.0
        answer='{"correct": "B"}',
    )
    db.add(q)
    db.flush()
    for label, text in [("A", "3"), ("B", "2"), ("C", "4"), ("D", "5")]:
        db.add(QuestionOption(question_id=q.id, option_label=label, option_content=text,
                              is_correct=(label == "B")))

    paper = ExamPaper(
        title="审计测试卷", subject_id=subject.id, created_by=student.id, status="published",
        config={"exam_title": "审计测试卷", "exam_status": "published",
                "student_ids": [student.id]},
    )
    db.add(paper)
    db.flush()
    db.add(ExamPaperQuestion(exam_paper_id=paper.id, question_id=q.id, order=0, score=3.0))
    db.commit()
    db.refresh(student)
    db.refresh(paper)

    client.post("/api/auth/login/json", json={"username": student.username, "password": "Str0ng!Pass"})
    return {"student": student, "paper": paper, "question": q}


def _answer_question_ids(client, exam_id):
    return client.get(f"/api/exams/{exam_id}/questions").json()["data"]


class TestAutoGradeOnSubmit:
    def test_submit_grades_objective_paper(self, client, db, student_with_exam):
        """纯客观卷交卷即 graded，得分按卷面分（3.0 而非题库默认 5.0）。"""
        paper = student_with_exam["paper"]
        rs = client.post(f"/api/exams/{paper.id}/start")
        assert rs.status_code in (200, 201), rs.json()
        rid = rs.json()["data"][0]["id"]
        questions = _answer_question_ids(client, paper.id)

        answers = [{"question_id": q["question_id"], "answer_content": "B"} for q in questions]
        r = client.post(f"/api/exams/{paper.id}/submit?exam_record_id={rid}", json=answers)
        assert r.status_code == 200

        data = r.json()["data"]
        assert data["status"] == "graded"
        assert float(data["score"]) == 3.0  # 卷面分而非题库默认 5.0

        mine = client.get("/api/exam-records").json()["data"]
        record = next(x for x in mine if x["id"] == rid)
        assert record["status"] == "graded"

    def test_wrong_answer_scores_zero(self, client, db, student_with_exam):
        """答错得 0 分且状态为 graded。"""
        paper = student_with_exam["paper"]
        rid = client.post(f"/api/exams/{paper.id}/start").json()["data"][0]["id"]
        questions = _answer_question_ids(client, paper.id)

        answers = [{"question_id": q["question_id"], "answer_content": "A"} for q in questions]
        r = client.post(f"/api/exams/{paper.id}/submit?exam_record_id={rid}", json=answers)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "graded"
        assert float(data["score"]) == 0.0


class TestExamWindow:
    def test_not_started_rejected(self, client, db, student_with_exam):
        """未开始的考试拒绝进入（datetime 解析比较）。"""
        from datetime import datetime, timedelta

        paper = student_with_exam["paper"]
        paper.config = {**paper.config, "start_time": (datetime.utcnow() + timedelta(days=1)).isoformat()}
        db.commit()

        r = client.get(f"/api/exams/{paper.id}/questions")
        assert r.status_code == 403
        body = r.json()
        msg = str(body.get("message") or body.get("detail") or body)
        assert "尚未开始" in msg
