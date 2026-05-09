# 智题 AIQuiz

AI 智能题库系统，支持 AI 出题、智能组卷、试题审核。

## 技术栈

- **后端**: Python 3.11 / FastAPI / SQLAlchemy / PostgreSQL
- **前端**: Vue 3 / Vite / Element Plus
- **AI服务**: MiniMax API
- **部署**: Docker / Docker Compose

## 项目结构

```
project/
├── backend/              # FastAPI 后端
│   └── app/              # 应用核心代码
├── frontend/             # Vue 3 前端
│   └── src/              # 源代码
├── deploy/               # Docker 部署配置
└── openspec/             # 变更管理
```

## 快速启动

### Docker 部署

```bash
cd deploy
cp .env.example .env
# 编辑 .env 配置 SECRET_KEY 和 MINIMAX_API_KEY
docker-compose up -d
```

访问 http://localhost:3000

### 本地开发

**后端：**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**前端：**
```bash
cd frontend
npm install
npm run dev
```

## 端口说明

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 3000 | 前端页面 |
| backend | 8000 | API 服务 |
| db | 5432 | PostgreSQL |

## 主要功能

- **AI 出题**: 选择知识点、题型、难度，AI 自动生成题目
- **智能组卷**: 设置参数自动组合试卷，支持 Word/PDF 导出
- **题库管理**: 题目 CRUD、批量导入、审核流程
- **用户权限**: 基于角色的权限控制