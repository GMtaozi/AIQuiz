# AI 自动出题系统

AI-powered exam question generation and exam management system.

## 技术栈

- **后端**: Python 3.11 / FastAPI / SQLAlchemy / PostgreSQL 15
- **前端**: Vue 3 / Vite / Element Plus
- **容器**: Docker / Docker Compose

## 项目结构

`
project/
├── backend/              # 后端服务
│   ├── app/              # 应用代码
│   ├── sql/              # SQL 脚本
│   ├── tests/            # 测试用例
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             # 前端服务
│   ├── src/              # 源代码
│   ├── Dockerfile
│   └── nginx.conf
├── deploy/               # 部署配置
│   ├── docker-compose.yml
│   ├── .env.example
│   └── init.sql
└── README.md
`

## 快速部署

### 前置条件

- Docker 20.10+
- Docker Compose v2+

### 启动步骤

`ash
cd deploy

# 复制环境变量文件并编辑
cp .env.example .env
# 编辑 .env，填入真实的 SECRET_KEY、MINIMAX_API_KEY、MINIMAX_GROUP_ID

# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps
`

访问 http://localhost:3000

### 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 3000 | 前端页面 |
| backend | 8000 | API 服务 |
| db | 5432 | PostgreSQL |
| redis | 6379 | Redis（预留） |

### 常用命令

`ash
# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 重启服务
docker-compose restart backend

# 停止服务
docker-compose down

# 清除所有数据（慎用）
docker-compose down -v
`

## 开发

### 后端

`ash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
`

### 前端

`ash
cd frontend
npm install
npm run dev
`

## 附加建议

1. **Redis**: 当前架构暂未使用 Redis，但已在 docker-compose.yml 中预留，方便后续扩展（缓存、Session 等）
2. **数据库备份**: 建议配置 PostgreSQL 定期备份策略，备份脚本可挂载到 deploy/backup/
3. **Nginx 反向代理**: 前端 Dockerfile 已内置 Nginx，无需额外配置；如果需要 HTTPS 或多域名，可在前面再加一层 Nginx
4. **健康检查**: PostgreSQL 配置了 healthcheck，确保数据库就绪后再启动后端
