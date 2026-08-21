# AIQuiz 后端服务

基于 FastAPI 的 AI 智能题库系统后端。

## 技术栈

- Python 3.11 / FastAPI / SQLAlchemy 2.0（同步会话）
- PostgreSQL 15 / Redis 7（限流与缓存）
- JWT 认证（httpOnly cookie 承载，Bearer 头兼容期保留）
- Alembic 数据库迁移

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写：

```bash
JWT_SECRET_KEY=<必填，python -c "import secrets; print(secrets.token_hex(32))" 生成>
DATABASE_URL=postgresql://postgres:password@localhost:5432/exam_system
MINIMAX_API_KEY=<AI 出题用>
```

> 注意：密钥名为 `JWT_SECRET_KEY`（应用启动时强制校验，缺失将拒绝启动）。

### 3. 初始化数据库

表结构由 Alembic 管理（**不使用** init.sql）：

```bash
alembic upgrade head
```

### 4. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 测试

```bash
pytest        # 单元 + 回归测试（TESTING=true 自动跳过密钥校验）
ruff check .  # Lint
```

## API 文档

本地开发设置 `ENABLE_DOCS=true` 后访问 http://localhost:8000/docs （生产默认关闭）。

## 目录结构

```
app/
├── main.py           # 应用入口（中间件/路由注册/lifespan）
├── config.py         # pydantic-settings 配置
├── database.py       # SQLAlchemy 会话
├── observability.py  # 结构化日志 + Sentry 接入点
├── models/           # ORM 模型（23 个）
├── routers/          # API 路由（按业务域拆分）
├── schemas/          # Pydantic 请求/响应模型
├── services/         # 业务逻辑（AI 出题/组卷/导出等）
└── utils/            # 安全/限流/统一响应等工具
```
