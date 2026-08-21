"""回归测试：覆盖评估报告中已修复的安全问题（P1-1/P1-3/P1-4/P1-6/P1-10 等）。

依赖 conftest 提供的 client（TestClient）与 db（Session）fixtures。
"""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeBase
from app.models.paper_template import PaperTemplate
from app.models.question import ExamPaper, GenerationTask
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.services.auth import AuthService


def _create_user(db: Session, username: str, role: int = 3, menu_permissions=None) -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=AuthService.get_password_hash("Test123456!"),
        role=role,
        menu_permissions=menu_permissions,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client: TestClient, username: str) -> str:
    resp = client.post("/api/auth/login/json", json={"username": username, "password": "Test123456!"})
    assert resp.status_code == 200
    body = resp.json()
    return body.get("data", body)["access_token"]


class TestCookieAuth:
    """P1-4：httpOnly cookie 认证流程"""

    def test_login_sets_cookie(self, client: TestClient, db: Session):
        _create_user(db, "cookie_user", role=1)
        resp = client.post("/api/auth/login/json", json={"username": "cookie_user", "password": "Test123456!"})
        assert resp.status_code == 200
        set_cookie = resp.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "HttpOnly" in set_cookie

    def test_me_with_cookie_only(self, client: TestClient, db: Session):
        """无 Authorization 头，仅凭 cookie 即可访问受保护接口"""
        _create_user(db, "cookie_me", role=1)
        resp = client.post("/api/auth/login/json", json={"username": "cookie_me", "password": "Test123456!"})
        assert resp.status_code == 200
        # httpx client 自动携带 set-cookie；不带 Authorization 头调用 /me
        resp2 = client.get("/api/auth/me")
        assert resp2.status_code == 200

    def test_logout_clears_cookie(self, client: TestClient, db: Session):
        _create_user(db, "cookie_out", role=1)
        client.post("/api/auth/login/json", json={"username": "cookie_out", "password": "Test123456!"})
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert "access_token=;" in resp.headers.get("set-cookie", "") or "access_token=" in resp.headers.get(
            "set-cookie", ""
        )
        resp2 = client.get("/api/auth/me")
        assert resp2.status_code == 401


class TestRegistrationNoPrivilege:
    """P1-6：注册用户无任何权限，直到管理员分配"""

    def test_register_returns_empty_permissions(self, client: TestClient, db: Session):
        resp = client.post(
            "/api/auth/register",
            json={"name": "newbie", "email": "newbie@test.com", "password": "Test123456!"},
        )
        assert resp.status_code == 200
        body = resp.json().get("data", resp.json())
        perms = body.get("menu_permissions")
        # 注册用户权限必须为空（列表或字典形式）
        if isinstance(perms, dict):
            assert all(v == [] for v in perms.values())
        else:
            assert not perms

    def test_registered_user_cannot_access_audit(self, client: TestClient, db: Session):
        """注册用户（role=3，无权限）访问需要 audit 权限的接口应被拒绝"""
        _create_user(db, "no_perm_user", role=3, menu_permissions=[])
        token = _login(client, "no_perm_user")
        resp = client.get("/api/audit/pending", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestTaskOwnership:
    """P1-3：任务接口归属校验（非本人任务返回 404）"""

    def test_progress_of_other_users_task_denied(self, client: TestClient, db: Session):
        owner = _create_user(db, "task_owner", role=2, menu_permissions=["ai-question"])
        other = _create_user(db, "task_other", role=2, menu_permissions=["ai-question"])
        task = GenerationTask(
            user_id=owner.id, status="completed", progress=100, mode="hybrid", result={"questions": [], "total": 0}
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        token = _login(client, "task_other")
        resp = client.get(f"/api/ai/task/{task.id}/progress", headers={"Authorization": f"Bearer {token}"})
        # 归属校验返回 404（防枚举），而非泄露他人任务内容
        assert resp.status_code == 404

    def test_owner_can_read_progress(self, client: TestClient, db: Session):
        owner = _create_user(db, "task_owner2", role=2, menu_permissions=["ai-question"])
        task = GenerationTask(
            user_id=owner.id, status="completed", progress=100, mode="hybrid", result={"questions": [], "total": 0}
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        token = _login(client, "task_owner2")
        resp = client.get(f"/api/ai/task/{task.id}/progress", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestExamOwnership:
    """P1-10：考试 update/delete 归属校验"""

    def test_non_owner_cannot_update_exam(self, client: TestClient, db: Session):
        owner = _create_user(db, "exam_owner", role=2)
        other = _create_user(db, "exam_other", role=2)
        paper = ExamPaper(title="测试试卷", subject_id=1, status="draft", created_by=owner.id, config={})
        db.add(paper)
        db.commit()
        db.refresh(paper)

        token = _login(client, "exam_other")
        resp = client.put(
            f"/api/exams/{paper.id}",
            json={"title": "篡改标题"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestTemplateVisibility:
    """P1-10：试卷模板可见性（非管理员仅公开/自己创建）"""

    def test_private_template_hidden_from_others(self, client: TestClient, db: Session):
        owner = _create_user(db, "tpl_owner", role=2)
        other = _create_user(db, "tpl_other", role=2)
        tpl = PaperTemplate(name="私有模板", subject_id=1, is_public=False, created_by=owner.id, status=1)
        db.add(tpl)
        db.commit()
        db.refresh(tpl)

        token = _login(client, "tpl_other")
        resp = client.get(f"/api/paper-templates/{tpl.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_public_template_visible_to_others(self, client: TestClient, db: Session):
        owner = _create_user(db, "tpl_owner2", role=2)
        other = _create_user(db, "tpl_other2", role=2)
        tpl = PaperTemplate(name="公开模板", subject_id=1, is_public=True, created_by=owner.id, status=1)
        db.add(tpl)
        db.commit()
        db.refresh(tpl)

        token = _login(client, "tpl_other2")
        resp = client.get(f"/api/paper-templates/{tpl.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestKnowledgeBaseVisibility:
    """P1-10：私有知识库不可被他人读取"""

    def test_private_kb_hidden_from_others(self, client: TestClient, db: Session):
        owner = _create_user(db, "kb_owner", role=2)
        other = _create_user(db, "kb_other", role=2)
        kb = KnowledgeBase(
            name="私有知识库", category="default", visibility="private", created_by=owner.id,
            status=1, source_file="x.docx", source_content="",
        )
        db.add(kb)
        db.commit()
        db.refresh(kb)

        token = _login(client, "kb_other")
        resp = client.get(f"/api/knowledge-bases/{kb.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403


class TestSettingsKeyMasking:
    """P0-12：API Key 等敏感设置不得明文返回"""

    def test_api_key_is_masked(self, client: TestClient, db: Session):
        _create_user(db, "mask_user", role=2)
        # upsert：system_settings.key 唯一约束，且 GET /settings 会 init_default_settings 建默认行
        existing = db.query(SystemSetting).filter(SystemSetting.key == "ai_api_key").first()
        if existing:
            existing.value = "sk-test-secret-123456"
        else:
            db.add(SystemSetting(key="ai_api_key", value="sk-test-secret-123456", type="string"))
        db.commit()

        token = _login(client, "mask_user")
        resp = client.get("/api/system/settings", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json().get("data", resp.json())
        settings = body.get("settings", body)
        masked = settings.get("ai_api_key", {}).get("value")
        # 掩码返回：非空密钥不回显明文
        assert masked is None or masked == "****" or masked == ""
        assert "sk-test-secret-123456" not in str(settings)

    def test_single_setting_key_masked(self, client: TestClient, db: Session):
        _create_user(db, "mask_user2", role=2)
        existing = db.query(SystemSetting).filter(SystemSetting.key == "ai_api_key").first()
        if existing:
            existing.value = "sk-secret-xyz"
        else:
            db.add(SystemSetting(key="ai_api_key", value="sk-secret-xyz", type="string"))
        db.commit()

        token = _login(client, "mask_user2")
        resp = client.get("/api/system/settings/ai_api_key", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json().get("data", resp.json())
        assert body.get("value") in (None, "", "****")
        assert "sk-secret-xyz" not in str(body)
