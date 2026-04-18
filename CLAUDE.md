# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**智题 AIQuiz** - 基于 FastAPI + Vue 3 的 AI 智能题库系统，支持 AI 出题、智能组卷、试题审核等功能。

## 技术栈

- **后端**: Python 3.11 / FastAPI / SQLAlchemy / PostgreSQL 15
- **前端**: Vue 3 / Vite / Element Plus / Pinia
- **AI服务**: MiniMax API (用于 AI 出题和知识点提取)
- **部署**: Docker / Docker Compose

## 项目结构

```
project/
├── backend/                    # FastAPI 后端
│   └── app/
│       ├── main.py            # 应用入口，路由注册
│       ├── config.py          # 配置管理 (pydantic-settings)
│       ├── database.py        # SQLAlchemy 会话管理
│       ├── models/            # SQLAlchemy ORM 模型
│       ├── routers/           # API 路由 (按功能模块划分)
│       ├── services/          # 业务逻辑 (AI出题、智能组卷等)
│       ├── schemas/           # Pydantic 请求/响应模型
│       └── utils/             # 工具函数
├── frontend/                  # Vue 3 前端
│   └── src/
│       ├── api/index.js       # API 调用封装 (axios)
│       ├── router/index.js    # 路由配置
│       ├── stores/            # Pinia 状态管理
│       └── views/admin/       # 管理员页面组件
├── deploy/                    # Docker 部署配置
└── openspec/                  # OpenSpec 变更管理
```

## 常用命令

### 后端开发 (本地)
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 前端开发 (本地)
```bash
cd frontend
npm install
npm run dev   # 端口 3008
```

### Docker 部署
```bash
cd deploy
docker-compose up -d
```

### 环境变量
后端 `.env` 文件 (位于 `D:\Project\AIsystem\backend\.env`):
- `DATABASE_URL`: 数据库连接 (默认 `sqlite:///./app.db`)
- `JWT_SECRET_KEY`: JWT 密钥
- `MINIMAX_API_KEY`: MiniMax AI API 密钥
- `CORS_ORIGINS`: 允许的跨域来源

## 架构要点

### API 设计
- 基础路径: `/api`
- 认证方式: JWT Bearer Token
- 错误处理: 统一返回 `detail` 字段，422 验证错误返回数组格式
- 文件下载: 使用 `StreamingResponse` + CORS headers

### 数据库
- ORM: SQLAlchemy with async support
- 同步使用: `SessionLocal`, `engine`
- 异步使用: `async_session_maker`, `async_engine`
- 初始化: `init_db()` 在 startup 事件中创建表

### 路由注册 (main.py)
路由按功能模块划分，统一注册到 `/api` 前缀:
- `/api/auth` - 认证
- `/api/papers` - 试卷管理
- `/api/questions` - 题目管理
- `/api/knowledge` - 知识点管理
- `/api/ai` - AI 出题
- `/api/audit` - 试题审核
- `/api/exams` - 考试管理
- `/api/dashboard` - 仪表盘
- `/api/system` - 系统设置、用户管理
- `/api/subjects` - 科目管理
- `/api/chapters` - 章节管理
- `/api/exam_records` - 考试记录

### 角色权限
- `admin` (role=1): 管理员，可管理题库、试卷、系统设置
- `teacher` (role=2): 教师，可出题、审核
- `student` (role=3): 学生，可考试、查看成绩

### 菜单权限系统
- 用户拥有独立的 `menu_permissions` 字段
- 路由守卫 `router/index.js` 检查权限：无权限用户跳转到 `/no-permission`
- 支持按用户分配个性化权限（可覆盖角色默认权限）

### 前端页面 (views/admin/)
- `DashboardView.vue` - 控制台
- `AIQuestionView.vue` - AI 出题
- `AuditView.vue` - 试题审核
- `AutoPaperView.vue` - 智能组卷
- `QuestionBankView.vue` - 题库管理
- `PaperManagementView.vue` - 试卷管理
- `KnowledgeView.vue` - 知识点管理
- `BatchKnowledgeView.vue` - 批量导入
- `UserPermissionView.vue` - 用户权限分配
- `SystemSettingsView.vue` - 系统设置

### AI 出题流程
1. 题目生成任务异步处理 (`GenerationTask` 表)
2. 前端轮询任务进度 (`/api/ai/task/{task_id}/progress`)
3. 任务完成后获取结果

### OpenSpec 变更管理
- 变更目录: `openspec/changes/`
- 归档目录: `openspec/changes/archive/`
- 使用 `/opsx:propose` 创建变更，`/opsx:apply` 实现，`/opsx:archive` 归档

## 关键文件

- `backend/app/routers/papers.py` - 试卷 CRUD + Word/PDF 导出
- `backend/app/services/paper_generator.py` - 智能组卷核心逻辑
- `backend/app/services/hybrid_question_generator.py` - 混合出题
- `frontend/src/views/admin/QuestionBankView.vue` - 题库管理页面
- `frontend/src/views/admin/PaperManagementView.vue` - 试卷管理页面
- `frontend/src/views/admin/AutoPaperView.vue` - 智能组卷页面
- `frontend/src/views/admin/UserPermissionView.vue` - 用户权限分配页面
