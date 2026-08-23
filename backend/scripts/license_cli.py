"""License 签发 CLI —— 仅供厂商内部使用（私钥绝不进入客户环境/代码仓库）。

用法:
    # 1. 生成密钥对（首次；公钥替换 license_service.py 内置值后发版）
    python -m scripts.license_cli keygen

    # 2. 签发授权
    python -m scripts.license_cli issue \\
        --private-key <hex> \\
        --licensee "某某教育科技有限公司" \\
        --edition professional \\
        --expires 2027-08-23 \\
        --max-users 200 \\
        --features ai_question knowledge_base template_market \\
        --out license.key

    expires 省略 = 永久授权；max-users 省略 = 不限用户数。
"""
import argparse
from datetime import date
import json
import sys
import uuid

FEATURE_CHOICES = ["ai_question", "knowledge_base", "template_market"]


def cmd_keygen(_args) -> int:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    priv = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    print("PRIVATE_KEY(hex) =", priv.hex())
    print("PUBLIC_KEY(hex)  =", pub.hex())
    print("\n下一步：将 PUBLIC_KEY 替换到 app/services/license_service.py 的 _BUILTIN_PUBLIC_KEY_HEX 后发版。")
    return 0


def cmd_issue(args) -> int:
    from app.services.license_service import KNOWN_FEATURES, PRODUCT_NAME, sign_payload

    unknown = set(args.features) - set(KNOWN_FEATURES)
    if unknown:
        print(f"未知特性: {unknown}，可选: {sorted(KNOWN_FEATURES)}", file=sys.stderr)
        return 1

    payload = {
        "licensee": args.licensee,
        "product": PRODUCT_NAME,
        "edition": args.edition,
        "issued_at": date.today().isoformat(),
        "expires_at": args.expires or None,
        "max_users": args.max_users,
        "features": sorted(set(args.features)),
        "nonce": str(uuid.uuid4()),
    }
    doc = {"payload": payload, "signature": sign_payload(payload, args.private_key)}
    output = json.dumps(doc, ensure_ascii=False, indent=2)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"已签发 -> {args.out}")
    else:
        print(output)

    print(f"\n客户: {payload['licensee']}  版本: {payload['edition']}")
    print(f"到期: {payload['expires_at'] or '永久'}  用户上限: {payload['max_users'] or '不限'}")
    print(f"特性: {payload['features']}")
    print("交付方式：将文件发给客户，管理员在 系统设置→授权管理 上传，或放置于 backend/license.key")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="AIQuiz License 签发工具（厂商内部）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("keygen", help="生成 Ed25519 密钥对")

    p_issue = sub.add_parser("issue", help="签发授权文件")
    p_issue.add_argument("--private-key", required=True, help="Ed25519 私钥 (hex)")
    p_issue.add_argument("--licensee", required=True, help="客户名称")
    p_issue.add_argument("--edition", default="standard",
                         choices=["standard", "professional", "enterprise"])
    p_issue.add_argument("--expires", help="到期日 YYYY-MM-DD（省略=永久）")
    p_issue.add_argument("--max-users", type=int, default=None, help="用户数上限（省略=不限）")
    p_issue.add_argument("--features", nargs="+", default=[], choices=FEATURE_CHOICES)
    p_issue.add_argument("--out", help="输出文件路径（省略=打印到 stdout）")

    args = parser.parse_args()
    return {"keygen": cmd_keygen, "issue": cmd_issue}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
