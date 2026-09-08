"""通知系统扩展功能测试

覆盖：
- EmailService 邮件发送（启用/禁用、类型过滤、配置不完整）
- PUT /api/notifications/read-all 标记全部已读
- DELETE /api/notifications/{id} 删除通知
- create_notification 邮件集成（创建通知时发送邮件）
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.notification import Notification
from app.models.user import User
from app.routers.notifications import create_notification
from app.services.auth import AuthService
from app.services.email_service import send_email_notification, should_send_email


# ============ Fixtures ============


@pytest.fixture()
def db():
    """Provide a fresh database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client():
    """Create test client."""
    return TestClient(app)


def _create_user(db: Session, username: str, role: int = 3) -> User:
    """Create a test user with upsert semantics."""
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        existing.role = role
        existing.status = 1
        db.commit()
        db.refresh(existing)
        return existing
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=AuthService.get_password_hash("Test123456!"),
        role=role,
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


def _create_notification(db: Session, user_id: int, notification_type: str = "info", title: str = "Test", content: str = "Content") -> Notification:
    """Create a test notification."""
    n = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        content=content,
        is_read=False,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


# ============ Email Service Tests ============


class TestEmailService:
    """Test email notification service."""

    def test_should_send_email_disabled_when_smtp_disabled(self):
        """SMTP 未启用时不发送邮件"""
        with patch.object(settings, "smtp_enabled", False):
            assert should_send_email("warning") is False

    def test_should_send_email_enabled_when_smtp_enabled(self):
        """SMTP 启用时发送邮件（warning 类型）"""
        with patch.object(settings, "smtp_enabled", True):
            assert should_send_email("warning") is True

    def test_should_send_email_skips_info_type(self):
        """info 类型不发送邮件"""
        with patch.object(settings, "smtp_enabled", True):
            assert should_send_email("info") is False

    def test_should_send_email_skips_success_type(self):
        """success 类型不发送邮件"""
        with patch.object(settings, "smtp_enabled", True):
            assert should_send_email("success") is False

    def test_should_send_email_sends_audit_type(self):
        """audit 类型发送邮件"""
        with patch.object(settings, "smtp_enabled", True):
            assert should_send_email("audit") is True

    def test_should_send_email_sends_error_type(self):
        """error 类型发送邮件"""
        with patch.object(settings, "smtp_enabled", True):
            assert should_send_email("error") is True

    def test_send_email_returns_false_when_disabled(self):
        """SMTP 未启用时返回 False"""
        with patch.object(settings, "smtp_enabled", False):
            result = send_email_notification("test@test.com", "Title", "Content", "warning")
        assert result is False

    def test_send_email_returns_false_for_info_type(self):
        """info 类型返回 False（不发邮件）"""
        with patch.object(settings, "smtp_enabled", True):
            result = send_email_notification("test@test.com", "Title", "Content", "info")
        assert result is False

    def test_send_email_returns_false_when_config_incomplete(self):
        """SMTP 配置不完整时返回 False"""
        with patch.object(settings, "smtp_enabled", True), \
             patch.object(settings, "smtp_host", ""), \
             patch.object(settings, "smtp_user", ""), \
             patch.object(settings, "smtp_password", ""):
            result = send_email_notification("test@test.com", "Title", "Content", "warning")
        assert result is False

    def test_send_email_success(self):
        """邮件发送成功返回 True"""
        mock_smtp = MagicMock()
        mock_context = MagicMock()
        mock_smtp.return_value = mock_context
        mock_context.__enter__ = MagicMock(return_value=mock_smtp)
        mock_context.__exit__ = MagicMock(return_value=False)

        with patch.object(settings, "smtp_enabled", True), \
             patch.object(settings, "smtp_host", "smtp.example.com"), \
             patch.object(settings, "smtp_port", 587), \
             patch.object(settings, "smtp_user", "user@example.com"), \
             patch.object(settings, "smtp_password", "password123"), \
             patch.object(settings, "smtp_from", "from@example.com"), \
             patch("app.services.email_service.smtplib.SMTP", mock_smtp):
            result = send_email_notification("test@test.com", "Title", "Content", "warning")
        assert result is True

    def test_send_email_handles_auth_failure(self):
        """SMTP 认证失败返回 False（不抛异常）"""
        mock_smtp_instance = MagicMock()
        mock_smtp_instance.starttls = MagicMock()
        mock_smtp_instance.login = MagicMock(side_effect=smtplib.SMTPAuthenticationError(535, b"Auth failed"))
        mock_smtp_instance.sendmail = MagicMock()

        mock_smtp_class = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(settings, "smtp_enabled", True), \
             patch.object(settings, "smtp_host", "smtp.example.com"), \
             patch.object(settings, "smtp_port", 587), \
             patch.object(settings, "smtp_user", "user@example.com"), \
             patch.object(settings, "smtp_password", "wrong"), \
             patch.object(settings, "smtp_from", "from@example.com"), \
             patch("app.services.email_service.smtplib.SMTP", mock_smtp_class):
            result = send_email_notification("test@test.com", "Title", "Content", "warning")
        assert result is False

    def test_send_email_handles_connection_failure(self):
        """SMTP 连接失败返回 False"""
        mock_smtp_class = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(side_effect=smtplib.SMTPConnectError(421, "Cannot connect"))
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(settings, "smtp_enabled", True), \
             patch.object(settings, "smtp_host", "smtp.example.com"), \
             patch.object(settings, "smtp_port", 587), \
             patch.object(settings, "smtp_user", "user@example.com"), \
             patch.object(settings, "smtp_password", "pass"), \
             patch.object(settings, "smtp_from", "from@example.com"), \
             patch("app.services.email_service.smtplib.SMTP", mock_smtp_class):
            result = send_email_notification("test@test.com", "Title", "Content", "warning")
        assert result is False

    def test_send_email_builds_correct_message(self):
        """验证邮件内容构建正确"""
        mock_smtp = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(settings, "smtp_enabled", True), \
             patch.object(settings, "smtp_host", "smtp.example.com"), \
             patch.object(settings, "smtp_port", 587), \
             patch.object(settings, "smtp_user", "user@example.com"), \
             patch.object(settings, "smtp_password", "pass"), \
             patch.object(settings, "smtp_from", "from@example.com"), \
             patch("app.services.email_service.smtplib.SMTP", mock_smtp):
            send_email_notification("to@test.com", "Test Title", "Test Content", "error")

        # 验证调用了 sendmail
        assert mock_smtp.sendmail.called
        call_args = mock_smtp.sendmail.call_args
        assert call_args[0][0] == "from@example.com"
        assert call_args[0][1] == ["to@test.com"]


# ============ API Endpoint Tests ============


class TestMarkAllAsRead:
    """Test PUT /api/notifications/read-all endpoint."""

    def test_mark_all_as_read_success(self, client: TestClient, db: Session):
        """标记全部已读成功"""
        user = _create_user(db, "mark_all_read_user")
        token = _login(client, "mark_all_read_user")
        headers = {"Authorization": f"Bearer {token}"}

        # Create multiple unread notifications
        for i in range(3):
            _create_notification(db, user.id, title=f"Notification {i}")

        # Verify all are unread
        unread_count = db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read == False).count()
        assert unread_count == 3

        # Mark all as read
        resp = client.put("/api/notifications/read-all", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("data", data)["message"] == "已全部标记为已读"

        # Verify all are now read
        unread_count = db.query(Notification).filter(Notification.user_id == user.id, Notification.is_read == False).count()
        assert unread_count == 0

    def test_mark_all_as_read_empty(self, client: TestClient, db: Session):
        """没有通知时标记全部已读也成功"""
        user = _create_user(db, "mark_all_empty_user")
        token = _login(client, "mark_all_empty_user")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.put("/api/notifications/read-all", headers=headers)
        assert resp.status_code == 200

    def test_mark_all_as_read_only_affects_current_user(self, client: TestClient, db: Session):
        """标记全部已读只影响当前用户的通知"""
        user1 = _create_user(db, "mark_all_user1")
        user2 = _create_user(db, "mark_all_user2")
        token1 = _login(client, "mark_all_user1")
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Create notifications for both users
        _create_notification(db, user1.id, title="User1 Notification")
        _create_notification(db, user2.id, title="User2 Notification")

        # Mark all as read for user1
        resp = client.put("/api/notifications/read-all", headers=headers1)
        assert resp.status_code == 200

        # User2's notification should still be unread
        user2_unread = db.query(Notification).filter(
            Notification.user_id == user2.id, Notification.is_read == False
        ).count()
        assert user2_unread == 1

    def test_mark_all_as_read_requires_auth(self, client: TestClient, db: Session):
        """标记全部已读需要认证"""
        resp = client.put("/api/notifications/read-all")
        assert resp.status_code == 401


class TestDeleteNotification:
    """Test DELETE /api/notifications/{id} endpoint."""

    def test_delete_notification_success(self, client: TestClient, db: Session):
        """删除通知成功"""
        user = _create_user(db, "delete_notif_user")
        token = _login(client, "delete_notif_user")
        headers = {"Authorization": f"Bearer {token}"}

        notif = _create_notification(db, user.id, title="To Delete")

        resp = client.delete(f"/api/notifications/{notif.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("data", data)["message"] == "删除成功"

        # Verify notification is deleted
        deleted = db.query(Notification).filter(Notification.id == notif.id).first()
        assert deleted is None

    def test_delete_notification_not_found(self, client: TestClient, db: Session):
        """删除不存在通知返回 404"""
        user = _create_user(db, "delete_notfound_user")
        token = _login(client, "delete_notfound_user")
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.delete("/api/notifications/99999", headers=headers)
        assert resp.status_code == 404

    def test_delete_notification_other_user_forbidden(self, client: TestClient, db: Session):
        """不能删除其他用户的通知"""
        user1 = _create_user(db, "delete_owner_user")
        user2 = _create_user(db, "delete_other_user")
        token2 = _login(client, "delete_other_user")
        headers2 = {"Authorization": f"Bearer {token2}"}

        notif = _create_notification(db, user1.id, title="Owner's Notification")

        resp = client.delete(f"/api/notifications/{notif.id}", headers=headers2)
        assert resp.status_code in (403, 404)

    def test_delete_notification_requires_auth(self, client: TestClient, db: Session):
        """删除通知需要认证"""
        resp = client.delete("/api/notifications/1")
        assert resp.status_code == 401


# ============ create_notification Integration Tests ============


class TestCreateNotificationWithEmail:
    """Test create_notification email integration."""

    def test_create_info_notification_no_email(self, db: Session):
        """创建 info 类型通知时不触发邮件"""
        user = _create_user(db, "info_notif_user")

        with patch("app.routers.notifications._send_email_notification_async") as mock_email:
            create_notification(
                db=db,
                notification_type="info",
                title="Info Title",
                content="Info Content",
                user_id=user.id,
            )
            mock_email.assert_not_called()

    def test_create_warning_notification_triggers_email(self, db: Session):
        """创建 warning 类型通知时触发邮件"""
        user = _create_user(db, "warn_notif_user")

        with patch("app.routers.notifications._send_email_notification_async") as mock_email:
            create_notification(
                db=db,
                notification_type="warning",
                title="Warning Title",
                content="Warning Content",
                user_id=user.id,
            )
            mock_email.assert_called_once()

    def test_create_error_notification_triggers_email(self, db: Session):
        """创建 error 类型通知时触发邮件"""
        user = _create_user(db, "error_notif_user")

        with patch("app.routers.notifications._send_email_notification_async") as mock_email:
            create_notification(
                db=db,
                notification_type="error",
                title="Error Title",
                content="Error Content",
                user_id=user.id,
            )
            mock_email.assert_called_once()

    def test_create_audit_notification_triggers_email(self, db: Session):
        """创建 audit 类型通知时触发邮件"""
        user = _create_user(db, "audit_notif_user")

        with patch("app.routers.notifications._send_email_notification_async") as mock_email:
            create_notification(
                db=db,
                notification_type="audit",
                title="Audit Title",
                content="Audit Content",
                user_id=user.id,
            )
            mock_email.assert_called_once()

    def test_create_notification_without_user_id_no_email(self, db: Session):
        """没有 user_id 时不触发邮件"""
        with patch("app.routers.notifications._send_email_notification_async") as mock_email:
            create_notification(
                db=db,
                notification_type="warning",
                title="System Notification",
                content="System Content",
                user_id=None,
            )
            mock_email.assert_not_called()

    def test_email_failure_does_not_break_notification_creation(self, db: Session):
        """邮件发送失败不影响通知创建"""
        user = _create_user(db, "email_fail_user")

        with patch(
            "app.routers.notifications._send_email_notification_async",
            side_effect=Exception("Email service unavailable"),
        ):
            # Should not raise
            notification = create_notification(
                db=db,
                notification_type="warning",
                title="Test",
                content="Test Content",
                user_id=user.id,
            )
            assert notification.id is not None
            assert notification.title == "Test"

    def test_email_async_function_queries_user_and_sends(self, db: Session):
        """异步邮件函数正确查询用户并发送邮件"""
        user = _create_user(db, "async_email_user")

        with patch("app.services.email_service.send_email_notification") as mock_send:
            from app.routers.notifications import _send_email_notification_async

            _send_email_notification_async(
                db=db,
                user_id=user.id,
                title="Test Title",
                content="Test Content",
                notification_type="warning",
            )
            mock_send.assert_called_once_with(
                user_email=user.email,
                title="Test Title",
                content="Test Content",
                notification_type="warning",
            )

    def test_email_async_function_no_user_no_send(self, db: Session):
        """用户不存在时不发送邮件"""
        with patch("app.services.email_service.send_email_notification") as mock_send:
            from app.routers.notifications import _send_email_notification_async

            _send_email_notification_async(
                db=db,
                user_id=99999,
                title="Test",
                content="Content",
                notification_type="warning",
            )
            mock_send.assert_not_called()


# ============ Notification Stats Tests ============


class TestNotificationStatsWithNewEndpoints:
    """Test stats endpoint after using read-all and delete."""

    def test_stats_after_mark_all_read(self, client: TestClient, db: Session):
        """标记全部已读后 stats 显示 unread=0"""
        user = _create_user(db, "stats_read_user")
        token = _login(client, "stats_read_user")
        headers = {"Authorization": f"Bearer {token}"}

        # Create unread notifications
        for i in range(3):
            _create_notification(db, user.id)

        # Mark all as read
        client.put("/api/notifications/read-all", headers=headers)

        # Check stats
        resp = client.get("/api/notifications/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["unread"] == 0

    def test_stats_after_delete(self, client: TestClient, db: Session):
        """删除通知后 stats 更新"""
        user = _create_user(db, "stats_del_user")
        token = _login(client, "stats_del_user")
        headers = {"Authorization": f"Bearer {token}"}

        notif1 = _create_notification(db, user.id, title="N1")
        notif2 = _create_notification(db, user.id, title="N2")

        # Delete one
        client.delete(f"/api/notifications/{notif1.id}", headers=headers)

        # Check stats
        resp = client.get("/api/notifications/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["total"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
