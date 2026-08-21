"""种子管理员初始化脚本。

在 Alembic 建表后运行，创建第一个管理员账号，使首次部署可登录。
独立于 Alembic 迁移（不纳入版本表），可重复运行（已存在则跳过）。

用法:
    cd backend
    python -m scripts.seed_admin --username admin --email admin@example.com

    # 或交互式（不传 --password 会提示输入）
    python -m scripts.seed_admin --username admin --email admin@example.com --role 1
"""

import argparse
import getpass
import sys

from app.database import SessionLocal
from app.models.user import User
from app.services.auth import AuthService


def main() -> int:
    parser = argparse.ArgumentParser(description="创建第一个管理员账号（幂等）")
    parser.add_argument("--username", required=True, help="用户名")
    parser.add_argument("--email", required=True, help="邮箱")
    parser.add_argument("--password", help="密码（不传则交互式输入）")
    parser.add_argument("--role", type=int, default=1, help="角色：1=管理员(默认) 2=编辑 3=审核员")
    args = parser.parse_args()

    password = args.password or getpass.getpass("请输入密码: ")

    db = SessionLocal()
    try:
        existing = db.query(User).filter((User.username == args.username) | (User.email == args.email)).first()
        if existing:
            print(f"跳过：用户已存在 (username={existing.username}, email={existing.email})")
            return 0

        from app.models.user import ROLE_DEFAULT_PERMISSIONS

        user = User(
            username=args.username,
            email=args.email,
            hashed_password=AuthService.get_password_hash(password),
            role=args.role,
            status=1,
            menu_permissions=ROLE_DEFAULT_PERMISSIONS.get(args.role, []),
        )
        db.add(user)
        db.commit()
        print(f"已创建用户: id={user.id} username={user.username} role={user.role}")
        return 0
    except Exception as e:
        db.rollback()
        print(f"创建失败: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
