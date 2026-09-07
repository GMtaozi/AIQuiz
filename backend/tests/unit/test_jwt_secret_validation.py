"""JWT 密钥强度校验回归（QA Critical：弱/短密钥可被用于自签 token 提权）。

背景：原 `validate_settings()` 只拦空值和 `change-me-in-production`，
`backend/.env` 里使用的 `dev-secret-key-for-testing-only-12345678` 可直接绕过校验；
而 `get_current_user` 完全信任 JWT 的 `sub`，拿到管理员 id 即获得完整管理员权限。

覆盖点：
1. 黑名单弱密钥在任何环境都被拒绝（含本次新增的 dev 值）；
2. 生产环境（debug=false）短于 32 字符被拒绝，开发环境不受长度限制；
3. 合法长密钥在两种环境都通过；
4. TESTING=true 时 validate_settings() 跳过校验（回归保护）；
5. 本地 .env 已完成密钥轮换（防止弱密钥被重新写回）。
"""

from pathlib import Path

import pytest

import app.config as config_module
from app.config import (
    MIN_PROD_JWT_SECRET_LENGTH,
    WEAK_JWT_SECRETS,
    Settings,
    validate_jwt_secret,
    validate_settings,
)

# 一个 64 字符（32 字节）的强密钥，仅用于测试
STRONG_SECRET = "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"

# 命中黑名单的两个关键值：原有占位值 + QA 报出的 dev 值
CRITICAL_WEAK_SECRETS = [
    "change-me-in-production",
    "dev-secret-key-for-testing-only-12345678",
]


class TestWeakSecretBlacklist:
    """黑名单内的弱密钥在任何环境都必须被拒绝。"""

    @pytest.mark.parametrize("secret", CRITICAL_WEAK_SECRETS)
    @pytest.mark.parametrize("debug", [True, False])
    def test_critical_weak_values_rejected(self, secret: str, debug: bool):
        with pytest.raises(ValueError) as exc:
            validate_jwt_secret(secret, debug)
        assert "弱密钥黑名单" in str(exc.value)

    def test_blacklist_contains_required_values(self):
        """黑名单必须包含本次要求的两项，防止后续被误删。"""
        assert "change-me-in-production" in WEAK_JWT_SECRETS
        assert "dev-secret-key-for-testing-only-12345678" in WEAK_JWT_SECRETS

    @pytest.mark.parametrize("secret", sorted(WEAK_JWT_SECRETS))
    def test_every_blacklisted_value_rejected_in_prod(self, secret: str):
        with pytest.raises(ValueError):
            validate_jwt_secret(secret, debug=False)

    def test_blacklist_is_case_insensitive(self):
        """大小写变体不能绕过黑名单。"""
        with pytest.raises(ValueError):
            validate_jwt_secret("CHANGE-ME-IN-PRODUCTION", debug=True)

    def test_error_message_is_actionable(self):
        """报错要给出可操作的生成命令。"""
        with pytest.raises(ValueError) as exc:
            validate_jwt_secret("dev-secret-key-for-testing-only-12345678", debug=True)
        assert "secrets.token_hex(32)" in str(exc.value)


class TestMissingSecret:
    @pytest.mark.parametrize("secret", ["", "   ", None])
    @pytest.mark.parametrize("debug", [True, False])
    def test_empty_secret_rejected(self, secret, debug: bool):
        with pytest.raises(ValueError) as exc:
            validate_jwt_secret(secret, debug)
        assert "未配置或为空" in str(exc.value)


class TestProductionLengthRule:
    """生产环境最小长度 32 字符，开发环境放宽。"""

    def test_prod_short_secret_rejected(self):
        short = "x" * (MIN_PROD_JWT_SECRET_LENGTH - 1)
        with pytest.raises(ValueError) as exc:
            validate_jwt_secret(short, debug=False)
        assert "长度不足" in str(exc.value)
        assert "secrets.token_hex(32)" in str(exc.value)

    def test_prod_exact_boundary_accepted(self):
        """恰好 32 字符应通过（边界值）。"""
        validate_jwt_secret("y" * MIN_PROD_JWT_SECRET_LENGTH, debug=False)

    def test_dev_short_secret_allowed(self):
        """开发环境允许短密钥，不能误伤本地开发。"""
        validate_jwt_secret("short-dev-key", debug=True)

    def test_strong_secret_passes_in_both_envs(self):
        validate_jwt_secret(STRONG_SECRET, debug=False)
        validate_jwt_secret(STRONG_SECRET, debug=True)

    def test_stripped_length_is_used(self):
        """带空白字符的 32 字符密钥按 strip 后长度判定，不应被误判为更长。"""
        padded = "  " + "y" * MIN_PROD_JWT_SECRET_LENGTH + "  "
        validate_jwt_secret(padded, debug=False)


class TestValidateSettingsTestingBypass:
    """validate_settings() 的 TESTING 提前 return 分支（回归保护）。"""

    @staticmethod
    def _install_weak_settings(monkeypatch) -> None:
        """让 get_settings() 返回一个弱密钥配置，绕开 @lru_cache 的影响。"""
        weak = Settings(
            _env_file=None,
            jwt_secret_key="dev-secret-key-for-testing-only-12345678",
            debug=True,
        )
        monkeypatch.setattr(config_module, "get_settings", lambda: weak)

    @pytest.mark.parametrize("testing_value", ["1", "true", "TRUE", "yes"])
    def test_testing_skips_validation(self, monkeypatch, testing_value: str):
        self._install_weak_settings(monkeypatch)
        monkeypatch.setenv("TESTING", testing_value)
        validate_settings()  # 不应抛出

    def test_without_testing_weak_secret_raises(self, monkeypatch):
        self._install_weak_settings(monkeypatch)
        monkeypatch.delenv("TESTING", raising=False)
        with pytest.raises(ValueError):
            validate_settings()

    def test_strong_secret_passes_without_testing(self, monkeypatch):
        strong = Settings(_env_file=None, jwt_secret_key=STRONG_SECRET, debug=False)
        monkeypatch.setattr(config_module, "get_settings", lambda: strong)
        monkeypatch.delenv("TESTING", raising=False)
        validate_settings()  # 不应抛出


class TestLocalEnvRotation:
    """本地 .env 必须已换成强密钥，否则启动会直接被新校验拦下。"""

    def test_local_env_secret_is_rotated(self):
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if not env_path.exists():
            pytest.skip("backend/.env 不存在（未使用本地配置文件）")

        content = env_path.read_text(encoding="utf-8", errors="ignore")
        secret = ""
        for line in content.splitlines():
            if line.startswith("JWT_SECRET_KEY="):
                secret = line.split("=", 1)[1].strip()
                break

        if not secret:
            pytest.skip("backend/.env 未配置 JWT_SECRET_KEY")

        assert secret.lower() not in WEAK_JWT_SECRETS, "本地 .env 仍在使用弱密钥"
        assert len(secret) >= MIN_PROD_JWT_SECRET_LENGTH, "本地 .env 密钥长度不足 32 字符"

    def test_repo_env_example_placeholder_is_blacklisted(self):
        """.env.example 的占位值必须在黑名单里，照抄示例配置会启动失败（有意为之）。"""
        example = Path(__file__).resolve().parents[2] / ".env.example"
        assert "your-jwt-secret-key-here" in WEAK_JWT_SECRETS
        if example.exists():
            content = example.read_text(encoding="utf-8", errors="ignore")
            assert "your-jwt-secret-key-here" in content
