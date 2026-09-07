"""P0 安全加固回归：认证 Cookie 的 Secure 标志配置化（backend/app/config.py）。

本文件由 QA 独立编写，用于验证「工程师自报的取值矩阵」是否真实成立，
不复用工程师已删除的临时脚本，也不采信其结论表格。

覆盖点：
1. 生产场景（DEBUG=false 且无显式覆盖）必须返回 True —— 本次修复的核心目的；
2. 显式 COOKIE_SECURE=false 必须能覆盖生产推导 —— 运维兜底路径；
3. TESTING 分支必须返回 False —— 否则认证类测试会因 cookie 不回传而全挂；
4. 端到端验证 Set-Cookie 响应头真的带上 Secure 属性。
"""

import pytest

from app.config import Settings


def _build(monkeypatch, **env) -> Settings:
    """按给定环境变量构造一个全新的 Settings 实例。

    _env_file=None 确保不受 backend/.env（含 DEBUG/COOKIE_SECURE）污染，
    每个用例的环境都是显式声明的，结果可复现。
    """
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


class TestCookieSecureMatrix:
    """独立复现工程师声称的 5 行矩阵，逐行验证。"""

    def test_local_dev_debug_true_returns_false(self, monkeypatch):
        """本地开发（DEBUG=true，无显式覆盖）→ False，否则 HTTP 下登录会静默失败。"""
        s = _build(monkeypatch, DEBUG="true", COOKIE_SECURE=None, TESTING=None)
        assert s.debug is True
        assert s.cookie_secure is None
        assert s.cookie_secure_flag is False

    def test_production_debug_false_returns_true(self, monkeypatch):
        """生产（DEBUG=false，无显式覆盖）→ True。这是本次 P0 修复的核心目的。"""
        s = _build(monkeypatch, DEBUG="false", COOKIE_SECURE=None, TESTING=None)
        assert s.debug is False
        assert s.cookie_secure is None
        assert s.cookie_secure_flag is True

    def test_explicit_true_overrides_debug_true(self, monkeypatch):
        """显式 COOKIE_SECURE=true 覆盖 DEBUG=true 的推导。"""
        s = _build(monkeypatch, DEBUG="true", COOKIE_SECURE="true", TESTING=None)
        assert s.cookie_secure is True
        assert s.cookie_secure_flag is True

    def test_explicit_false_overrides_debug_false(self, monkeypatch):
        """显式 COOKIE_SECURE=false 覆盖生产推导 —— 运维兜底路径必须可用。"""
        s = _build(monkeypatch, DEBUG="false", COOKIE_SECURE="false", TESTING=None)
        assert s.cookie_secure is False
        assert s.cookie_secure_flag is False

    @pytest.mark.parametrize("testing_value", ["1", "true", "TRUE", "yes"])
    def test_testing_env_always_false(self, monkeypatch, testing_value):
        """TESTING 为真时恒为 False（即便 DEBUG=false），否则认证类测试全挂。"""
        s = _build(monkeypatch, DEBUG="false", COOKIE_SECURE=None, TESTING=testing_value)
        assert s.cookie_secure_flag is False

    def test_testing_does_not_override_explicit_true(self, monkeypatch):
        """显式配置优先级高于 TESTING 分支：显式 true + TESTING → True。"""
        s = _build(monkeypatch, DEBUG="false", COOKIE_SECURE="true", TESTING="true")
        assert s.cookie_secure_flag is True


class TestCookieSecureParsing:
    """环境变量取值解析的健壮性（bool | None 三态）。"""

    @pytest.mark.parametrize("raw", ["true", "True", "TRUE", "1", "yes"])
    def test_truthy_variants(self, monkeypatch, raw):
        s = _build(monkeypatch, DEBUG="true", COOKIE_SECURE=raw, TESTING=None)
        assert s.cookie_secure is True
        assert s.cookie_secure_flag is True

    @pytest.mark.parametrize("raw", ["false", "False", "FALSE", "0", "no"])
    def test_falsy_variants(self, monkeypatch, raw):
        s = _build(monkeypatch, DEBUG="false", COOKIE_SECURE=raw, TESTING=None)
        assert s.cookie_secure is False
        assert s.cookie_secure_flag is False

    def test_omitted_means_autoderive(self, monkeypatch):
        """变量完全不设置时 cookie_secure 为 None（走自动推导），不是 False。"""
        s = _build(monkeypatch, DEBUG="false", COOKIE_SECURE=None, TESTING=None)
        assert s.cookie_secure is None  # 区别于显式 False
        assert s.cookie_secure_flag is True


class TestSetAuthCookieEndToEnd:
    """端到端：_set_auth_cookie 真的把 secure 写进了响应头。"""

    @staticmethod
    def _cookie_header(monkeypatch, cookie_secure) -> str:
        from fastapi.responses import JSONResponse

        from app.config import Settings
        from app.routers import auth as auth_module

        fake_settings = Settings(_env_file=None, cookie_secure=cookie_secure)
        monkeypatch.setattr(auth_module, "settings", fake_settings)

        response = auth_module._set_auth_cookie(JSONResponse({"ok": True}), "fake.jwt.token")
        return response.headers["set-cookie"]

    def test_secure_flag_present_when_enabled(self, monkeypatch):
        header = self._cookie_header(monkeypatch, True)
        assert "Secure" in header
        assert "HttpOnly" in header
        assert "access_token=fake.jwt.token" in header

    def test_secure_flag_absent_when_disabled(self, monkeypatch):
        header = self._cookie_header(monkeypatch, False)
        assert "Secure" not in header
        assert "HttpOnly" in header  # 其余安全属性不能被顺手改坏
        assert "access_token=fake.jwt.token" in header
