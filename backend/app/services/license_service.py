"""License 授权服务 —— 私有化部署的商业化核心。

设计：
- 离线授权文件（license.key）：Ed25519 签名，客户无法伪造/篡改/自行续期
- 公钥内置 + 环境变量 LICENSE_PUBLIC_KEY 可覆盖（换钥/测试场景）
- 无授权文件 → 试用模式（TRIAL_DAYS 天，起始时间记于 system_settings）
- 试用期届满 → 增值功能拒绝（AI 出题等），登录与数据查看不受影响
  （不锁死客户数据是商业软件惯例，避免法律纠纷）

License 文件格式:
    {"payload": {...}, "signature": "<base64 ed25519>"}
payload 字段:
    licensee     客户名称
    product      固定 "AIQuiz"
    edition      standard / professional / enterprise
    issued_at    签发日期 YYYY-MM-DD
    expires_at   到期日期或 null（永久授权）
    max_users    用户数上限，null 为不限
    features     特性列表 ["ai_question", ...]
    nonce        随机串
"""
import base64
from datetime import date, datetime
import json
import logging
import os

logger = logging.getLogger(__name__)

PRODUCT_NAME = "AIQuiz"
TRIAL_DAYS = 30

# 正式发布钥对的公钥（私钥由厂商线下保管，泄露时换钥发新版）
_BUILTIN_PUBLIC_KEY_HEX = "46e41009ef35552d8150b0388cc76e79b3461c09ac760135492ebd7a7a84a0a5"

# 已知特性清单（签发时按 edition 裁剪）
KNOWN_FEATURES = {
    "ai_question",       # AI 出题
    "knowledge_base",    # 知识库
    "template_market",   # 模板市场
}


class LicenseInfo(dict):
    """规范化后的授权状态（dict 子类，便于直接 JSON 序列化）。"""


def _get_public_key() -> bytes:
    """环境变量 LICENSE_PUBLIC_KEY 优先于内置公钥。"""
    hex_key = os.environ.get("LICENSE_PUBLIC_KEY") or _BUILTIN_PUBLIC_KEY_HEX
    return bytes.fromhex(hex_key)


def _canonical_payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def parse_license_file(content: str) -> tuple[dict | None, str]:
    """解析并验签 license 内容。

    返回 (payload, error)：有效时 error 为空串；无效时 payload 为 None。
    任何异常都归为"无效授权"，绝不因授权文件问题导致服务崩溃。
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        doc = json.loads(content)
        payload = doc["payload"]
        signature = base64.b64decode(doc["signature"])
        if payload.get("product") != PRODUCT_NAME:
            return None, f"产品不匹配: {payload.get('product')}"
        Ed25519PublicKey.from_public_bytes(_get_public_key()).verify(
            signature, _canonical_payload_bytes(payload)
        )
        return payload, ""
    except (KeyError, ValueError, json.JSONDecodeError):
        return None, "授权文件格式无效"
    except InvalidSignature:
        return None, "授权签名验证失败"
    except Exception as e:  # 授权解析兜底，见 docstring
        return None, f"授权解析异常: {e}"


def sign_payload(payload: dict, private_key_hex: str) -> str:
    """签发侧工具（scripts/license_cli.py 使用）：对 payload 生成签名。"""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    sig = key.sign(_canonical_payload_bytes(payload))
    return base64.b64encode(sig).decode()


def _trial_started_at(db) -> datetime:
    """读取（首次时创建）试用起始时间，存于 system_settings 表。"""
    from app.models.system_setting import SystemSetting

    row = db.query(SystemSetting).filter(SystemSetting.key == "trial_started_at").first()
    if row and row.value:
        try:
            return datetime.fromisoformat(row.value)
        except ValueError:
            pass
    now = datetime.now()
    if row:
        row.value = now.isoformat()
    else:
        db.add(SystemSetting(
            key="trial_started_at", value=now.isoformat(), type="string",
            description="试用模式起始时间",
        ))
    db.commit()
    return now


class LicenseService:
    """进程内单例：启动加载；管理端更新授权后调用 reload()。"""

    def __init__(self):
        self._state: LicenseInfo | None = None

    def load(self, db=None) -> LicenseInfo:
        """从 config.license_file 路径加载授权；无效则进入试用模式判定。"""
        from app.config import settings as app_settings

        state: LicenseInfo = LicenseInfo(mode="invalid")
        path = app_settings.license_file
        if path and os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    payload, err = parse_license_file(f.read())
                if payload:
                    state = LicenseInfo(
                        mode="expired" if self._is_expired(payload) else "licensed",
                        licensee=payload.get("licensee", ""),
                        edition=payload.get("edition", ""),
                        issued_at=payload.get("issued_at"),
                        expires_at=payload.get("expires_at"),
                        max_users=payload.get("max_users"),
                        features=list(payload.get("features") or []),
                    )
                else:
                    state = LicenseInfo(mode="invalid", error=err)
                    logger.warning(f"授权文件无效: {err}")
            except OSError as e:
                logger.warning(f"授权文件读取失败: {e}")

        if state["mode"] == "invalid":
            state.update(self._trial_state(db))
        self._state = state
        logger.info(f"License 状态: mode={state['mode']}")
        return state

    def reload(self, db=None) -> LicenseInfo:
        return self.load(db)

    @property
    def state(self) -> LicenseInfo:
        if self._state is None:
            raise RuntimeError("License 尚未加载（应在应用启动时调用 load()）")
        return self._state

    # ---------- 判定 ----------
    @staticmethod
    def _is_expired(payload: dict) -> bool:
        expires = payload.get("expires_at")
        if not expires:
            return False
        try:
            return date.today() > date.fromisoformat(str(expires))
        except ValueError:
            return True  # 非法日期按过期处理，宁严勿松

    def _trial_state(self, db) -> dict:
        """试用模式状态：剩余天数与是否超期。

        db 为 None 时（无法访问 DB 的极端场景）视为未超期，保持可用。
        """
        info: dict = {"mode": "trial", "licensee": "（试用期）", "edition": "trial"}
        if db is None:
            info.update(features=sorted(KNOWN_FEATURES), max_users=None, trial_expired=False)
            return info
        started = _trial_started_at(db)
        expired = (datetime.now() - started).days >= TRIAL_DAYS
        info.update(
            trial_started_at=started.date().isoformat(),
            trial_days_left=max(0, TRIAL_DAYS - (datetime.now() - started).days),
            features=[] if expired else sorted(KNOWN_FEATURES),
            max_users=None,
            trial_expired=expired,
        )
        return info

    def feature_enabled(self, feature: str) -> bool:
        """增值特性是否可用：licensed 看签名 features；trial 看 trial_expired。"""
        st = self.state
        if st["mode"] == "licensed":
            return feature in st["features"]
        if st["mode"] == "trial":
            return not st.get("trial_expired", False)
        return False

    def user_limit_reached(self, current_users: int) -> bool:
        """是否达到用户数上限（license.max_users；试用/未配置不限）。"""
        limit = self.state.get("max_users")
        return bool(limit and current_users >= limit)


license_service = LicenseService()
