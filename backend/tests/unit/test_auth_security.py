"""Unit tests for auth security utilities."""

from datetime import timedelta

from fastapi import HTTPException
import pytest

from app.services.auth import AuthService
from app.utils.security import verify_token


class TestPasswordRoundtrip:
    def test_hash_and_verify(self):
        raw = "MyStr0ng!P@ss"
        hashed = AuthService.get_password_hash(raw)
        assert hashed != raw
        assert AuthService.verify_password(raw, hashed) is True

    def test_wrong_password_fails(self):
        hashed = AuthService.get_password_hash("correct")
        assert AuthService.verify_password("wrong", hashed) is False

    def test_empty_password(self):
        hashed = AuthService.get_password_hash("")
        assert AuthService.verify_password("", hashed) is True


class TestTokenRoundtrip:
    def test_create_and_verify(self):
        token = AuthService.create_access_token(data={"sub": "1"})
        payload = verify_token(token)
        assert payload is not None
        assert payload.get("sub") == "1"

    def test_expired_token(self):
        token = AuthService.create_access_token(data={"sub": "1"}, expires_delta=timedelta(minutes=-10))
        with pytest.raises(HTTPException):
            verify_token(token)

    def test_tampered_token(self):
        token = AuthService.create_access_token(data={"sub": "1"}) + "x"
        with pytest.raises(HTTPException):
            verify_token(token)

    def test_missing_sub(self):
        """verify_token returns payload; sub check happens in get_current_user."""
        token = AuthService.create_access_token(data={"other": "v"})
        payload = verify_token(token)
        assert "sub" not in payload  # sub is absent but decode succeeds
