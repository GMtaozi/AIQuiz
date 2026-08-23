"""商业化地基回归测试：权限单一来源 + 学生语义 + 任务队列降级。

背景（2026-08 商业化第二阶段）：
- role=3 语义定为"学生"：默认无任何管理端菜单权限
- 权限权威来源收敛到 models.user.ROLE_DEFAULT_PERMISSIONS
- 管理接口准入收窄为 require_editor_or_admin（role 1/2）
- 登录/refresh 响应下发扁平数组权限
"""
import pytest

from app.models.user import ROLE_DEFAULT_PERMISSIONS, User
from app.utils.security import (
    require_editor_or_admin,
    require_teacher_or_admin,
)


class TestRoleSemantics:
    """role=3 = 学生 的语义统一回归。"""

    def test_student_default_permissions_empty(self):
        """学生角色默认无任何管理端菜单权限。"""
        assert ROLE_DEFAULT_PERMISSIONS[3] == []

    def test_editor_or_admin_rejects_student(self, db):
        """require_editor_or_admin 拒绝学生访问管理接口。"""
        student = User(
            username="perm_student",
            email="perm_student@test.com",
            hashed_password="x",
            role=3,
            status=1,
            menu_permissions=[],
        )
        db.add(student)
        db.commit()
        db.refresh(student)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            require_editor_or_admin(student)
        assert exc.value.status_code == 403

    def test_editor_or_admin_accepts_editor_and_admin(self, db):
        """教师与管理员可正常通过 require_editor_or_admin。"""
        admin = User(username="pa", email="pa@test.com", hashed_password="x", role=1, status=1)
        teacher = User(username="pt", email="pt@test.com", hashed_password="x", role=2, status=1)
        db.add_all([admin, teacher])
        db.commit()
        db.refresh(admin)
        db.refresh(teacher)

        assert require_editor_or_admin(admin).id == admin.id
        assert require_editor_or_admin(teacher).id == teacher.id

    def test_legacy_alias_points_to_same_dependency(self):
        """历史别名 require_teacher_or_admin 与新依赖同源（已收窄）。"""
        assert require_teacher_or_admin is require_editor_or_admin


class TestPermissionSingleSource:
    """权限判定唯一来源：models.user.ROLE_DEFAULT_PERMISSIONS。"""

    def test_require_permission_uses_authoritative_table_for_none(self, db):
        """menu_permissions=None 的存量用户按角色默认表判定（学生→拒绝）。"""
        legacy = User(
            username="perm_none",
            email="perm_none@test.com",
            hashed_password="x",
            role=3,
            status=1,
            menu_permissions=None,
        )
        db.add(legacy)
        db.commit()
        db.refresh(legacy)

        from app.utils.security import require_permission

        dep = require_permission("audit")
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            dep(legacy)
        assert exc.value.status_code == 403

    def test_explicit_grant_overrides_role_default(self, db):
        """个性化授权优先于角色默认（学生被显式授予 audit 则放行）。"""
        granted = User(
            username="perm_grant",
            email="perm_grant@test.com",
            hashed_password="x",
            role=3,
            status=1,
            menu_permissions=["audit"],
        )
        db.add(granted)
        db.commit()
        db.refresh(granted)

        from app.utils.security import require_permission

        dep = require_permission("audit")
        assert dep(granted).id == granted.id


class TestAuthResponseFlatPermissions:
    """登录/注册响应下发扁平数组权限（前端不再解析角色映射）。"""

    def test_register_returns_flat_empty_permissions(self, client):
        r = client.post("/api/auth/register", json={
            "name": "flatreg",
            "email": "flatreg@test.com",
            "password": "Str0ng!Passw0rd",
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert isinstance(data["menu_permissions"], list)
        assert data["menu_permissions"] == []
        assert data["needs_admin_approval"] is True

    def test_login_returns_flat_effective_permissions(self, client, db):
        u = User(
            username="flatlogin",
            email="flatlogin@test.com",
            hashed_password="$2b$12$KIX/DeN7.1vbePfBUnS6UuJm3R9GqZzWj0pQ4Yy5Xz8AaBbCcDdEe",
            role=2,
            status=1,
            menu_permissions=["ai-question", "audit"],
        )
        db.add(u)
        db.commit()

        # 用真实密码重设 hash（避免手工构造 bcrypt 串的脆弱性）
        from app.services.auth import AuthService

        u.hashed_password = AuthService.get_password_hash("Str0ng!Passw0rd")
        db.commit()

        r = client.post("/api/auth/login/json", json={"username": "flatlogin", "password": "Str0ng!Passw0rd"})
        assert r.status_code == 200
        data = r.json()["data"]
        assert isinstance(data["menu_permissions"], list)
        assert set(data["menu_permissions"]) == {"ai-question", "audit"}
