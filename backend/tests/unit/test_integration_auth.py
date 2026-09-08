"""Integration tests for the Auth module.

Covers: register, login, logout, refresh, get profile, forgot password.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


class TestAuthRegister:
    """POST /api/auth/register - Register new user."""

    def test_register_success(self, client: TestClient, db: Session):
        payload = {
            "name": "newuser",
            "email": "newuser@test.com",
            "password": "Str0ng!Passw0rd",
        }
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["role"] == 3  # Student by default
        assert data["menu_permissions"] == []
        assert data["needs_admin_approval"] is True

    def test_register_duplicate_email(self, client: TestClient, db: Session):
        _create_user(db, "existing_user", role=3)
        payload = {
            "name": "newuser",
            "email": "existing_user@test.com",
            "password": "Str0ng!Passw0rd",
        }
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 400

    def test_register_and_login_flow(self, client: TestClient, db: Session):
        """Test complete registration and login flow."""
        # Register
        register_payload = {
            "name": "flowuser",
            "email": "flowuser@test.com",
            "password": "Str0ng!Passw0rd",
        }
        resp = client.post("/api/auth/register", json=register_payload)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["role"] == 3
        assert data["menu_permissions"] == []

        # Login with the registered user
        login_payload = {"username": "flowuser", "password": "Str0ng!Passw0rd"}
        resp = client.post("/api/auth/login/json", json=login_payload)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data


class TestAuthLogin:
    """POST /api/auth/login/json - Login with JSON."""

    def test_login_success(self, client: TestClient, db: Session):
        _create_user(db, "login_user", role=1)
        payload = {"username": "login_user", "password": "Test123456!"}
        resp = client.post("/api/auth/login/json", json=payload)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client: TestClient, db: Session):
        _create_user(db, "login_wrong_pw", role=1)
        payload = {"username": "login_wrong_pw", "password": "WrongPassword!"}
        resp = client.post("/api/auth/login/json", json=payload)
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient, db: Session):
        payload = {"username": "nonexistent", "password": "Test123456!"}
        resp = client.post("/api/auth/login/json", json=payload)
        assert resp.status_code == 401

    def test_login_disabled_user(self, client: TestClient, db: Session):
        user = _create_user(db, "disabled_user", role=1)
        user.status = 0
        db.commit()
        payload = {"username": "disabled_user", "password": "Test123456!"}
        resp = client.post("/api/auth/login/json", json=payload)
        assert resp.status_code == 403


class TestAuthLogout:
    """POST /api/auth/logout - Logout."""

    def test_logout(self, client: TestClient, db: Session):
        _create_user(db, "logout_user", role=1)
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 200


class TestAuthRefresh:
    """POST /api/auth/refresh - Refresh token."""

    def test_refresh_token(self, client: TestClient, db: Session):
        _create_user(db, "refresh_user", role=1)
        token = _login(client, "refresh_user")
        resp = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "access_token" in data

    def test_refresh_without_token(self, client: TestClient, db: Session):
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 401


class TestAuthMe:
    """GET /api/auth/me - Get current user profile."""

    def test_get_me(self, client: TestClient, db: Session):
        _create_user(db, "me_user", role=1)
        token = _login(client, "me_user")
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_get_me_unauthenticated(self, client: TestClient, db: Session):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestAuthForgotPassword:
    """POST /api/auth/forgot-password - Forgot password."""

    def test_forgot_password(self, client: TestClient, db: Session):
        payload = {"username": "forgot_user"}
        resp = client.post("/api/auth/forgot-password", json=payload)
        assert resp.status_code == 200

    def test_forgot_password_nonexistent(self, client: TestClient, db: Session):
        payload = {"username": "nonexistent_user"}
        resp = client.post("/api/auth/forgot-password", json=payload)
        assert resp.status_code == 200  # Should not reveal if user exists
