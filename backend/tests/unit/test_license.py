"""License 授权机制回归测试：签发/验签/篡改/过期/门控/用户上限/API。"""
import base64
from datetime import date, timedelta
import json
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest


@pytest.fixture()
def keypair(monkeypatch):
    """生成测试密钥对并注入为受信公钥。"""
    from app.services import license_service as ls

    priv = Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()
    monkeypatch.setenv("LICENSE_PUBLIC_KEY", pub_hex)
    return {
        "private_hex": priv.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
        ).hex(),
        "public_hex": pub_hex,
    }


def make_license(private_hex: str, **overrides) -> dict:
    from app.services.license_service import PRODUCT_NAME, sign_payload

    payload = {
        "licensee": "测试教育机构",
        "product": PRODUCT_NAME,
        "edition": "professional",
        "issued_at": date.today().isoformat(),
        "expires_at": (date.today() + timedelta(days=365)).isoformat(),
        "max_users": 100,
        "features": ["ai_question"],
        "nonce": str(uuid.uuid4()),
    }
    payload.update(overrides)
    return {"payload": payload, "signature": sign_payload(payload, private_hex)}


class TestSignAndVerify:
    def test_roundtrip_valid(self, keypair):
        from app.services.license_service import parse_license_file

        doc = make_license(keypair["private_hex"])
        payload, err = parse_license_file(json.dumps(doc))
        assert err == ""
        assert payload["licensee"] == "测试教育机构"
        assert payload["features"] == ["ai_question"]

    def test_tampered_payload_rejected(self, keypair):
        from app.services.license_service import parse_license_file

        doc = make_license(keypair["private_hex"])
        doc["payload"]["features"] = ["ai_question", "knowledge_base"]  # 私自加特性
        payload, err = parse_license_file(json.dumps(doc))
        assert payload is None
        assert "签名" in err

    def test_wrong_key_rejected(self, keypair):
        from app.services.license_service import parse_license_file

        other = Ed25519PrivateKey.generate()
        other_hex = other.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
        ).hex()
        doc = make_license(other_hex)  # 用非受信私钥签发
        payload, _err = parse_license_file(json.dumps(doc))
        assert payload is None

    def test_garbage_input_rejected(self):
        from app.services.license_service import parse_license_file

        payload, err = parse_license_file("not a json")
        assert payload is None and err


class TestExpiry:
    def test_expired_license_detected(self, keypair):
        from app.services.license_service import LicenseService, parse_license_file

        svc = LicenseService()
        doc = make_license(keypair["private_hex"], expires_at=(date.today() - timedelta(days=1)).isoformat())
        payload, _ = parse_license_file(json.dumps(doc))
        assert svc._is_expired(payload) is True

    def test_permanent_license_never_expires(self, keypair):
        from app.services.license_service import LicenseService, parse_license_file

        svc = LicenseService()
        doc = make_license(keypair["private_hex"], expires_at=None)
        payload, _ = parse_license_file(json.dumps(doc))
        assert svc._is_expired(payload) is False


class TestFeatureGating:
    def _svc_with_state(self, mode: str, **extra):
        from app.services.license_service import LicenseInfo, LicenseService

        svc = LicenseService()
        svc._state = LicenseInfo(mode=mode, **extra)
        return svc

    def test_licensed_feature_in_list(self):
        svc = self._svc_with_state("licensed", features=["ai_question"])
        assert svc.feature_enabled("ai_question") is True
        assert svc.feature_enabled("knowledge_base") is False

    def test_trial_not_expired_allows(self):
        svc = self._svc_with_state("trial", trial_expired=False)
        assert svc.feature_enabled("ai_question") is True

    def test_trial_expired_denies(self):
        svc = self._svc_with_state("trial", trial_expired=True)
        assert svc.feature_enabled("ai_question") is False

    def test_invalid_mode_denies(self):
        svc = self._svc_with_state("invalid")
        assert svc.feature_enabled("ai_question") is False


class TestUserLimit:
    def test_limit_enforced(self):
        from app.services.license_service import LicenseInfo, LicenseService

        svc = LicenseService()
        svc._state = LicenseInfo(mode="licensed", max_users=10)
        assert svc.user_limit_reached(10) is True
        assert svc.user_limit_reached(9) is False

    def test_unlimited_when_none(self):
        from app.services.license_service import LicenseInfo, LicenseService

        svc = LicenseService()
        svc._state = LicenseInfo(mode="trial", max_users=None)
        assert svc.user_limit_reached(99999) is False


class TestLicenseAPI:
    def test_get_status_requires_admin(self, client):
        # 未登录 → 401/403
        r = client.get("/api/system/license")
        assert r.status_code in (401, 403)

    def test_upload_invalid_content_rejected(self, client, db):
        from app.models.user import ROLE_DEFAULT_PERMISSIONS, User
        from app.services.auth import AuthService

        admin = User(
            username="lic_admin", email="lic_admin@test.com", role=1, status=1,
            hashed_password=AuthService.get_password_hash("Str0ng!Pass"),
            menu_permissions=ROLE_DEFAULT_PERMISSIONS[1],
        )
        db.add(admin)
        db.commit()

        client.post("/api/auth/login/json", json={"username": "lic_admin", "password": "Str0ng!Pass"})
        r = client.post("/api/system/license/upload", json={"content": "garbage"})
        assert r.status_code == 400
        body = r.json()
        # 统一 envelope：message 可能在顶层或 data 内
        msg = str(body.get("message") or (body.get("data") or {}).get("message") or body)
        assert "无效" in msg
