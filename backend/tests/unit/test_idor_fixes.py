"""回归测试：IDOR 资源归属校验修复（P1-10）。

验证各模块的非所有者访问返回 403/404，防止越权操作。
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeBase, KnowledgePoint
from app.models.question import AIPromptTemplate, ExamPaper, ExamPaperQuestion, Question, QuestionOption, Subject, Chapter
from app.models.user import User
from app.services.auth import AuthService


def _create_user(db: Session, username: str, role: int = 3, menu_permissions=None) -> User:
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


def _create_subject_and_chapter(db: Session) -> tuple[Subject, Chapter]:
    """Create a subject and chapter for testing."""
    subject = db.query(Subject).filter(Subject.code == "IDOR_TEST_SUBJ").first()
    if not subject:
        subject = Subject(name="IDOR Test Subject", code="IDOR_TEST_SUBJ", status=1)
        db.add(subject)
        db.commit()
        db.refresh(subject)
    chapter = db.query(Chapter).filter(Chapter.code == "IDOR_TEST_CHAP").first()
    if not chapter:
        chapter = Chapter(subject_id=subject.id, name="IDOR Test Chapter", code="IDOR_TEST_CHAP", order=0, status=1)
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
        title="IDOR Test Paper",
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


# ===========================================================================
# Papers Module IDOR Tests
# ===========================================================================


class TestPapersIDOR:
    """P1-10：试卷模块资源归属校验"""

    def test_update_paper_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能更新他人试卷"""
        owner = _create_user(db, "paper_owner_idor", role=2)
        other = _create_user(db, "paper_other_idor", role=2)
        paper = _create_paper(db, owner.id, status="draft")
        token = _login(client, "paper_other_idor")
        resp = client.put(
            f"/api/papers/{paper.id}",
            json={"title": "Hacked Title"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_delete_paper_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能删除他人试卷"""
        owner = _create_user(db, "paper_del_owner", role=2)
        other = _create_user(db, "paper_del_other", role=2)
        paper = _create_paper(db, owner.id, status="draft")
        token = _login(client, "paper_del_other")
        resp = client.delete(
            f"/api/papers/{paper.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_publish_paper_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能发布他人试卷"""
        owner = _create_user(db, "paper_pub_owner", role=2)
        other = _create_user(db, "paper_pub_other", role=2)
        paper = _create_paper(db, owner.id, status="draft")
        token = _login(client, "paper_pub_other")
        resp = client.post(
            f"/api/papers/{paper.id}/publish",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_analysis_paper_non_owner_draft_forbidden(self, client: TestClient, db: Session):
        """非所有者不能查看他人草稿试卷的分析"""
        owner = _create_user(db, "paper_anal_owner", role=2)
        other = _create_user(db, "paper_anal_other", role=2)
        paper = _create_paper(db, owner.id, status="draft")
        token = _login(client, "paper_anal_other")
        resp = client.get(
            f"/api/papers/{paper.id}/analysis",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_similarity_check_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能检测他人试卷相似度"""
        owner = _create_user(db, "paper_sim_owner", role=2)
        other = _create_user(db, "paper_sim_other", role=2)
        paper = _create_paper(db, owner.id, status="draft")
        token = _login(client, "paper_sim_other")
        resp = client.post(
            f"/api/papers/{paper.id}/similarity-check",
            json={"paper_id": paper.id, "threshold": 0.7},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_export_paper_non_owner_draft_forbidden(self, client: TestClient, db: Session):
        """非所有者不能导出他人草稿试卷"""
        owner = _create_user(db, "paper_exp_owner", role=2)
        other = _create_user(db, "paper_exp_other", role=2)
        paper = _create_paper(db, owner.id, status="draft")
        token = _login(client, "paper_exp_other")
        resp = client.post(
            "/api/papers/export",
            json={"paper_id": paper.id, "format": "word"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ===========================================================================
# Knowledge Bases Module IDOR Tests
# ===========================================================================


class TestKnowledgeBasesIDOR:
    """P1-10：知识库模块资源归属校验"""

    def test_update_kb_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能更新他人知识库"""
        owner = _create_user(db, "kb_owner_idor", role=2)
        other = _create_user(db, "kb_other_idor", role=2)
        kb = KnowledgeBase(
            name="Private KB", category="default", visibility="private",
            created_by=owner.id, status=1, source_file="x.docx", source_content="",
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        token = _login(client, "kb_other_idor")
        resp = client.put(
            f"/api/knowledge-bases/{kb.id}",
            json={"name": "Hacked KB"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_delete_kb_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能删除他人知识库"""
        owner = _create_user(db, "kb_del_owner", role=2)
        other = _create_user(db, "kb_del_other", role=2)
        kb = KnowledgeBase(
            name="Private KB", category="default", visibility="private",
            created_by=owner.id, status=1, source_file="x.docx", source_content="",
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        token = _login(client, "kb_del_other")
        resp = client.delete(
            f"/api/knowledge-bases/{kb.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_upload_kb_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能上传文档到他人知识库"""
        owner = _create_user(db, "kb_up_owner", role=2)
        other = _create_user(db, "kb_up_other", role=2)
        kb = KnowledgeBase(
            name="Private KB", category="default", visibility="private",
            created_by=owner.id, status=1, source_file="x.docx", source_content="",
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        token = _login(client, "kb_up_other")
        # Create a small test file
        file_content = b"Test document content for upload"
        resp = client.post(
            f"/api/knowledge-bases/{kb.id}/upload",
            files={"file": ("test.txt", file_content, "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_list_entries_non_owner_private_forbidden(self, client: TestClient, db: Session):
        """非所有者不能查看私有知识库条目"""
        owner = _create_user(db, "kb_ent_owner", role=2)
        other = _create_user(db, "kb_ent_other", role=2)
        kb = KnowledgeBase(
            name="Private KB", category="default", visibility="private",
            created_by=owner.id, status=1, source_file="x.docx", source_content="",
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        token = _login(client, "kb_ent_other")
        resp = client.get(
            f"/api/knowledge-bases/{kb.id}/entries",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_analyze_entry_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能分析他人知识库条目"""
        from app.models.knowledge import KnowledgeEntry

        owner = _create_user(db, "kb_anl_owner", role=2)
        other = _create_user(db, "kb_anl_other", role=2)
        kb = KnowledgeBase(
            name="Private KB", category="default", visibility="private",
            created_by=owner.id, status=1, source_file="x.docx", source_content="",
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        # Create an entry for the KB
        entry = KnowledgeEntry(
            knowledge_base_id=kb.id,
            title="Test Entry",
            content="Test content for analysis",
            order=0,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        token = _login(client, "kb_anl_other")
        resp = client.post(
            f"/api/knowledge-bases/{kb.id}/entries/{entry.id}/analyze",
            json={"mode": "rule", "max_points": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_analyze_all_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能批量分析他人知识库"""
        owner = _create_user(db, "kb_aa_owner", role=2)
        other = _create_user(db, "kb_aa_other", role=2)
        kb = KnowledgeBase(
            name="Private KB", category="default", visibility="private",
            created_by=owner.id, status=1, source_file="x.docx", source_content="",
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        token = _login(client, "kb_aa_other")
        resp = client.post(
            f"/api/knowledge-bases/{kb.id}/analyze-all",
            json={"mode": "rule", "max_points": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_list_points_non_owner_private_forbidden(self, client: TestClient, db: Session):
        """非所有者不能查看私有知识库知识点"""
        owner = _create_user(db, "kb_pts_owner", role=2)
        other = _create_user(db, "kb_pts_other", role=2)
        kb = KnowledgeBase(
            name="Private KB", category="default", visibility="private",
            created_by=owner.id, status=1, source_file="x.docx", source_content="",
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)
        token = _login(client, "kb_pts_other")
        resp = client.get(
            f"/api/knowledge-bases/{kb.id}/points",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ===========================================================================
# Knowledge Points Module IDOR Tests
# ===========================================================================


class TestKnowledgePointsIDOR:
    """P1-10：知识点模块资源归属校验"""

    def test_get_knowledge_point_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能查看他人知识点"""
        owner = _create_user(db, "kp_owner_idor", role=2)
        other = _create_user(db, "kp_other_idor", role=2)
        kp = KnowledgePoint(
            name="Private KP", category="default", created_by=owner.id, status=1
        )
        db.add(kp)
        db.commit()
        db.refresh(kp)
        token = _login(client, "kp_other_idor")
        resp = client.get(
            f"/api/knowledge/{kp.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_update_knowledge_point_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能更新他人知识点"""
        owner = _create_user(db, "kp_up_owner", role=2)
        other = _create_user(db, "kp_up_other", role=2)
        kp = KnowledgePoint(
            name="Private KP", category="default", created_by=owner.id, status=1
        )
        db.add(kp)
        db.commit()
        db.refresh(kp)
        token = _login(client, "kp_up_other")
        resp = client.put(
            f"/api/knowledge/{kp.id}",
            json={"name": "Hacked KP"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_delete_knowledge_point_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能删除他人知识点"""
        owner = _create_user(db, "kp_del_owner", role=2)
        other = _create_user(db, "kp_del_other", role=2)
        kp = KnowledgePoint(
            name="Private KP", category="default", created_by=owner.id, status=1
        )
        db.add(kp)
        db.commit()
        db.refresh(kp)
        token = _login(client, "kp_del_other")
        resp = client.delete(
            f"/api/knowledge/{kp.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ===========================================================================
# AI Templates Module IDOR Tests
# ===========================================================================


class TestAITemplatesIDOR:
    """P1-10：AI 模板模块资源归属校验"""

    def test_update_template_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能更新他人模板"""
        owner = _create_user(db, "tpl_owner_idor", role=2)
        other = _create_user(db, "tpl_other_idor", role=2)
        tpl = AIPromptTemplate(
            name="Private Template",
            template_type="question_generation",
            prompt_template="Generate questions about {{topic}}",
            status="active",
            created_by=owner.id,
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        token = _login(client, "tpl_other_idor")
        resp = client.put(
            f"/api/ai/templates/{tpl.id}",
            json={"name": "Hacked Template"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_delete_template_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能删除他人模板"""
        owner = _create_user(db, "tpl_del_owner", role=2)
        other = _create_user(db, "tpl_del_other", role=2)
        tpl = AIPromptTemplate(
            name="Private Template",
            template_type="question_generation",
            prompt_template="Generate questions about {{topic}}",
            status="active",
            created_by=owner.id,
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        token = _login(client, "tpl_del_other")
        resp = client.delete(
            f"/api/ai/templates/{tpl.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_get_inactive_template_non_owner_forbidden(self, client: TestClient, db: Session):
        """非所有者不能查看非活跃模板"""
        owner = _create_user(db, "tpl_inactive_owner", role=2)
        other = _create_user(db, "tpl_inactive_other", role=2)
        tpl = AIPromptTemplate(
            name="Inactive Template",
            template_type="question_generation",
            prompt_template="Generate questions about {{topic}}",
            status="inactive",
            created_by=owner.id,
        )
        db.add(tpl)
        db.commit()
        db.refresh(tpl)
        token = _login(client, "tpl_inactive_other")
        resp = client.get(
            f"/api/ai/templates/{tpl.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


# ===========================================================================
# Audit Module IDOR Tests
# ===========================================================================


class TestAuditIDOR:
    """P1-10：审核模块权限校验"""

    def test_get_question_for_audit_no_permission_forbidden(self, client: TestClient, db: Session):
        """无审核权限的用户不能获取审核题目详情"""
        user = _create_user(db, "audit_noperm", role=3, menu_permissions=[])
        subject, chapter = _create_subject_and_chapter(db)
        q = _create_question(db, chapter, subject, user.id)
        token = _login(client, "audit_noperm")
        resp = client.get(
            f"/api/audit/{q.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_get_audit_logs_no_permission_forbidden(self, client: TestClient, db: Session):
        """无审核权限的用户不能获取审核日志"""
        user = _create_user(db, "audit_logs_noperm", role=3, menu_permissions=[])
        subject, chapter = _create_subject_and_chapter(db)
        q = _create_question(db, chapter, subject, user.id)
        token = _login(client, "audit_logs_noperm")
        resp = client.get(
            f"/api/audit/{q.id}/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    def test_get_audit_statistics_no_permission_forbidden(self, client: TestClient, db: Session):
        """无审核权限的用户不能获取审核统计"""
        user = _create_user(db, "audit_stats_noperm", role=3, menu_permissions=[])
        token = _login(client, "audit_stats_noperm")
        resp = client.get(
            "/api/audit/statistics/summary",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
