"""P0 修复回归测试：验证此前必 500/404 的模块恢复可用。

覆盖：schemas/paper 常量、crud 路由遮蔽、paper_versions 前缀、批量接口、audit_logs。
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.question import Chapter, ExamPaper, GenerationTask, Question, Subject
from app.models.user import User
from app.services.auth import AuthService


def _create_user(db: Session, username: str, role: int = 1, menu_permissions=None) -> User:
    # upsert：测试共享 session 级数据库，同名用户复用并更新角色
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        existing.role = role
        existing.menu_permissions = menu_permissions
        db.commit()
        db.refresh(existing)
        return existing
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


def _admin_token(client: TestClient, db: Session) -> str:
    _create_user(db, "p0admin", role=1)
    return _login(client, "p0admin")


class TestPaperModule:
    """P0-9：schemas/paper 常量修复后试卷模块恢复"""

    def test_paper_list_works(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/papers/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json().get("data", resp.json())
        assert "items" in body or "papers" in body or isinstance(body, list)

    def test_paper_detail_works(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        paper = ExamPaper(title="回归测试卷", subject_id=1, status="draft", created_by=1, config={})
        db.add(paper)
        db.commit()
        db.refresh(paper)
        resp = client.get(f"/api/papers/{paper.id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestQuestionRoutes:
    """P0-10：静态路由不再被 /{question_id} 遮蔽"""

    def test_statistics_route_works(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.get("/api/questions/statistics", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_batch_delete_works(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        resp = client.post(
            "/api/questions/batch-delete",
            json={"ids": [99999]},  # 不存在的 id 也应返回正常响应而非 500
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestPaperVersionsRoute:
    """P0-11：paper_versions 补 /api 前缀后路由可达"""

    def test_versions_route_registered(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        paper = ExamPaper(title="版本测试卷", subject_id=1, status="draft", created_by=1, config={})
        db.add(paper)
        db.commit()
        db.refresh(paper)
        resp = client.get(
            f"/api/paper-versions/{paper.id}/versions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestAuditLogTable:
    """P0-13：audit_logs 表存在且审核接口可写日志"""

    def test_audit_endpoint_reachable(self, client: TestClient, db: Session):
        token = _admin_token(client, db)
        # 待审核列表接口（依赖 audit_logs 的读路径在批量审核中，此处验证列表可用）
        resp = client.get("/api/audit/pending", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestGenerationTaskColumn:
    """P0 附加修复：GenerationTask.total_questions 列存在，任务进度可读"""

    def test_task_progress_owner_readable(self, client: TestClient, db: Session):
        owner = _create_user(db, "task_col_owner", role=2, menu_permissions=["ai-question"])
        task = GenerationTask(
            user_id=owner.id,
            status="completed",
            progress=100,
            mode="hybrid",
            result={"questions": [], "total": 0},
            total_questions=0,
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        token = _login(client, "task_col_owner")
        resp = client.get(f"/api/ai/task/{task.id}/progress", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
