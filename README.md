# 智题 AIQuiz

AI 智能题库系统，支持 AI 出题、智能组卷、试题审核、在线考试。

## 技术栈

- **后端**: Python 3.11 / FastAPI / SQLAlchemy 2.0 / PostgreSQL 15 / Redis 7
- **前端**: Vue 3 / Vite / Element Plus / Pinia
- **AI服务**: MiniMax API（多服务商可扩展）
- **部署**: Docker / Docker Compose
- **数据库迁移**: Alembic

## 项目结构

```
project/
├── backend/              # FastAPI 后端
│   ├── app/              # 应用核心代码
│   ├── alembic/          # 数据库迁移
│   └── tests/            # 测试套件
├── frontend/             # Vue 3 前端
│   └── src/              # 源代码
├── deploy/               # Docker 部署配置 + 备份脚本
└── openspec/             # 变更管理
```

## 快速启动

### Docker 部署（推荐）

```bash
cd deploy
cp .env.example .env
# 编辑 .env，必须配置: JWT_SECRET_KEY、POSTGRES_PASSWORD、MINIMAX_API_KEY
# 生成 JWT 密钥: python -c "import secrets; print(secrets.token_hex(32))"
docker compose up -d
```

访问 http://localhost:3000 。数据库表结构由 backend 容器启动时自动执行 `alembic upgrade head` 创建。

### 本地开发

**后端：**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # 编辑 .env 配置 JWT_SECRET_KEY 与 DATABASE_URL
alembic upgrade head   # 初始化数据库表结构
uvicorn app.main:app --reload --port 8000
# 另开终端启动 AI 出题任务队列 worker（Redis 需可用）:
arq app.worker.WorkerSettings
```

**前端：**
```bash
cd frontend
npm install
npm run dev   # 端口 3008，API 代理到 localhost:8000
```

### 运行测试

```bash
cd backend
pytest            # 56 个测试（单元 + 回归）
```

```bash
cd frontend
npm run typecheck # TypeScript 类型检查
```

## 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 3000 | 前端页面 |
| backend | 8000 | API 服务 |
| db | 5432 | PostgreSQL（仅绑定 127.0.0.1） |
| redis | 6380 | Redis（限流/缓存，仅绑定 127.0.0.1） |

## 数据库备份

```bash
# 手动备份
deploy/backup.sh

# 每日定时备份（宿主机 crontab）
# 0 2 * * * /opt/AIQuiz/deploy/backup.sh >> /var/log/aiquiz-backup.log 2>&1
```

## 主要功能

- **AI 出题**: 知识点驱动的混合出题引擎（规则定策略 + AI 生成 + 模板兜底）
- **智能组卷**: 参数化自动组卷、难度分布、A/B 卷、Word/PDF 导出
- **题库管理**: 题目 CRUD、Excel/Word 批量导入导出、相似度查重
- **试题审核**: 审核流、审核日志、通知创建者
- **知识库**: 文档上传、AI/规则双通道知识点提取
- **在线考试**: 组卷发布、在线作答、客观题自动判分
- **用户权限**: 三角色 + 用户级菜单权限控制
