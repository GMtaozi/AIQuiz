# 智题 AIQuiz 生产环境部署指南

> 适用版本：v1.0.0 | 架构：FastAPI + Vue 3 + PostgreSQL + Redis + Docker Compose

---

## 目录

1. [前置要求](#1-前置要求)
2. [快速部署步骤](#2-快速部署步骤)
3. [生产环境配置](#3-生产环境配置)
4. [数据库管理](#4-数据库管理)
5. [监控与告警](#5-监控与告警)
6. [故障排查](#6-故障排查)
7. [安全清单](#7-安全清单)

---

## 1. 前置要求

### 1.1 服务器配置要求

| 资源 | 最低配置 | 推荐配置 | 说明 |
|------|----------|----------|------|
| CPU | 2 核 | 4 核 | AI 出题任务需要 CPU 资源 |
| 内存 | 4 GB | 8 GB | PostgreSQL + Redis + Backend + Worker |
| 磁盘 | 50 GB SSD | 100 GB SSD | 数据库 + 备份 + 日志 |
| 网络 | 10 Mbps | 100 Mbps | AI API 调用需要稳定网络 |

### 1.2 依赖软件

```bash
# Docker Engine 24.0+
docker --version
# Docker Engine 24.0.x

# Docker Compose v2.20+（必须是 v2 插件，不是 docker-compose v1）
docker compose version
# Docker Compose version v2.20.x

# Git（拉取代码）
git --version
```

### 1.3 域名和 SSL 证书准备

| 项目 | 说明 | 示例 |
|------|------|------|
| 主域名 | 前端访问入口 | `aiquiz.example.com` |
| API 子域名（可选） | 反向代理后端 | `api.aiquiz.example.com` |
| SSL 证书 | Let's Encrypt 或商业证书 | `/etc/letsencrypt/live/aiquiz.example.com/fullchain.pem` |
| SSL 私钥 | 对应私钥 | `/etc/letsencrypt/live/aiquiz.example.com/privkey.pem` |

```bash
# 使用 Certbot 快速获取 Let's Encrypt 证书
sudo apt install certbot
sudo certbot certonly --standalone -d aiquiz.example.com
```

---

## 2. 快速部署步骤

### 2.1 克隆仓库

```bash
cd /opt
git clone <仓库地址> AIQuiz
cd AIQuiz
# 切换到生产分支
git checkout main
```

### 2.2 配置环境变量

```bash
# 进入部署目录
cd /opt/AIsystem/deploy

# 生成 JWT 密钥（必须！长度 ≥ 32 字符）
python3 -c "import secrets; print(secrets.token_hex(32))"
# 输出示例：a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2

# 创建 .env 文件
cat > .env << 'EOF'
# ========== 核心密钥 ==========
JWT_SECRET_KEY=<上一步生成的64字符密钥>
POSTGRES_PASSWORD=<数据库强密码>

# ========== 可选配置 ==========
POSTGRES_DB=exam_system
POSTGRES_USER=postgres
MINIMAX_API_KEY=<MiniMax AI API Key>
CORS_ORIGINS=["https://aiquiz.example.com"]

# ========== 可观测性 ==========
SENTRY_DSN=<Sentry DSN，留空则禁用>
ENVIRONMENT=production
LOG_JSON=true
EOF
```

### 2.3 Docker Compose 启动

```bash
# 在 deploy 目录下执行
cd /opt/AIsystem/deploy

# 构建并启动所有服务
docker compose up -d --build

# 查看启动日志
docker compose logs -f

# 确认所有服务健康
docker compose ps
```

预期输出：

```
NAME                STATUS
aiquiz-backend-1    Up 30s (healthy)
aiquiz-worker-1    Up 28s
aiquiz-frontend-1  Up 25s (healthy)
aiquiz-db-1        Up 35s (healthy)
aiquiz-redis-1     Up 32s (healthy)
```

### 2.4 数据库迁移

> **注意**：backend 容器启动时会自动执行 `alembic upgrade head`，无需手动运行。

如果迁移失败（例如 JWT_SECRET_KEY 配置错误），手动修复步骤：

```bash
# 进入 backend 容器
docker compose exec backend bash

# 手动执行迁移
alembic upgrade head

# 查看当前版本
alembic current

# 查看历史
alembic history --verbose

# 退出容器
exit
```

### 2.5 验证服务正常

```bash
# 1. 后端健康检查
curl http://localhost:8000/health
# 预期：{"status":"healthy"}

# 2. API 根路径
curl http://localhost:8000/
# 预期：{"message":"AI Question System API","version":"1.0.0"}

# 3. 前端访问
curl http://localhost:3000/health
# 预期：healthy

# 4. 前端页面（浏览器访问）
# http://localhost:3000

# 5. 数据库连接检查
docker compose exec db pg_isready -U postgres

# 6. Redis 连接检查
docker compose exec redis redis-cli ping
```

---

## 3. 生产环境配置

### 3.1 Docker Compose 生产环境优化

`deploy/docker-compose.yml` 已包含以下生产级配置，无需额外修改：

```yaml
# 关键配置说明：
services:
  backend:
    restart: unless-stopped          # 自动重启策略
    healthcheck:                     # 健康检查
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:                     # 资源限制
        limits:
          cpus: '1'
          memory: 1G

  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
```

### 3.2 Nginx 反向代理配置（SSL 终止 + 静态文件服务）

在宿主机部署 Nginx 作为反向代理，处理 SSL 终止和前端静态文件：

```nginx
# /etc/nginx/conf.d/aiquiz.conf

upstream backend_servers {
    server 127.0.0.1:8000;
    keepalive 32;
}

upstream frontend_servers {
    server 127.0.0.1:3000;
}

# HTTP → HTTPS 跳转
server {
    listen 80;
    server_name aiquiz.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name aiquiz.example.com;

    # SSL 配置
    ssl_certificate /etc/letsencrypt/live/aiquiz.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/aiquiz.example.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;

    # 安全响应头（与后端 security_headers 中间件互补）
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Strict-Transport-Security "max-age=63072000" always;

    # 前端 SPA 入口
    location / {
        proxy_pass http://frontend_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API 代理（保留 /api 前缀）
    location /api/ {
        proxy_pass http://backend_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;  # AI 出题任务可能需要较长时间
        proxy_connect_timeout 10s;
    }

    # Auth 路由代理
    location /auth/ {
        proxy_pass http://backend_servers;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket（如未来需要）
    location /ws/ {
        proxy_pass http://backend_servers;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # 静态资源长期缓存（frontend nginx.conf 已处理，此处为兜底）
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2)$ {
        proxy_pass http://frontend_servers;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 3.3 PostgreSQL 性能配置

创建自定义配置文件 `deploy/postgresql.conf`：

```ini
# 根据服务器内存调整（示例：4GB 内存服务器）
# shared_buffers = 25% 内存 = 1GB
shared_buffers = 1GB

# effective_cache_size = 50-75% 内存 = 3GB
effective_cache_size = 3GB

# work_mem = 每连接排序内存（连接数 × work_mem ≤ 50% 内存）
# 假设 max_connections = 100, work_mem = 4MB
work_mem = 4MB

# maintenance_work_mem = VACUUM/ CREATE INDEX 等操作内存
maintenance_work_mem = 256MB

# 连接配置
max_connections = 100
listen_addresses = '*'

# WAL 配置（平衡性能与持久性）
wal_level = replica
synchronous_commit = on
wal_buffers = 16MB

# 日志配置
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_min_duration_statement = 1000  # 记录超过 1s 的慢查询

# 自动清理
autovacuum = on
autovacuum_max_workers = 3
```

将配置挂载到 docker-compose.yml（db 服务添加 volumes）：

```yaml
  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgresql.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
```

### 3.4 Redis 持久化配置

创建 `deploy/redis.conf`：

```ini
# 持久化配置（RDB + AOF 双保险）
save 900 1
save 300 10
save 60 10000

appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
no-appendfsync-on-rewrite yes

# 内存限制（与 docker-compose resources 一致）
maxmemory 256mb
maxmemory-policy allkeys-lru

# 安全
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command DEBUG ""
```

挂载到 docker-compose.yml（redis 服务添加 volumes）：

```yaml
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf
    command: redis-server /usr/local/etc/redis/redis.conf
```

---

## 4. 数据库管理

### 4.1 Alembic 迁移命令

```bash
# 查看当前版本
docker compose exec backend alembic current

# 查看迁移历史
docker compose exec backend alembic history --verbose

# 升级到最新版本
docker compose exec backend alembic upgrade head

# 回退一个版本
docker compose exec backend alembic downgrade -1

# 回退到指定版本
docker compose exec backend alembic downgrade <revision>

# 生成新迁移（开发阶段使用）
docker compose exec backend alembic revision --autogenerate -m "描述"

# 查看 SQL 变更（不执行）
docker compose exec backend alembic upgrade head --sql
```

### 4.2 备份策略

项目已内置 `deploy/backup.sh` 脚本，配置宿主机 cron 定时执行：

```bash
# 1. 编辑 crontab
sudo crontab -e

# 2. 添加每日凌晨 2 点备份（保留 14 天）
0 2 * * * /opt/AIsystem/deploy/backup.sh >> /var/log/aiquiz-backup.log 2>&1

# 3. 查看备份目录
ls -lh /opt/AIsystem/deploy/backups/
```

脚本默认配置（可通过环境变量覆盖）：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `BACKUP_DIR` | `deploy/backups` | 备份输出目录 |
| `RETENTION_DAYS` | `14` | 备份保留天数 |
| `POSTGRES_DB` | `exam_system` | 数据库名 |
| `POSTGRES_USER` | `postgres` | 数据库用户 |

### 4.3 恢复流程

```bash
# 1. 停止写入服务
docker compose stop backend worker

# 2. 找到最新备份
ls -lt /opt/AIsystem/deploy/backups/*.sql.gz | head -1

# 3. 恢复（将 <file> 替换为实际备份文件名）
gunzip -c /opt/AIsystem/deploy/backups/<file>.sql.gz | \
  docker compose exec -T db psql -U postgres exam_system

# 4. 重启服务
docker compose start backend worker

# 5. 验证数据完整性
docker compose exec backend python -c "
from app.database import SessionLocal
db = SessionLocal()
print(f'Users: {db.execute(\"SELECT count(*) FROM users\").scalar()}')
db.close()
"
```

---

## 5. 监控与告警

### 5.1 健康检查端点

| 端点 | 用途 | 预期响应 |
|------|------|----------|
| `GET /health` | 后端服务健康 | `{"status":"healthy"}` |
| `GET /` | API 根路径 | `{"message":"AI Question System API","version":"1.0.0"}` |

Docker Compose 已配置自动健康检查，`docker compose ps` 显示 `healthy/unhealthy` 状态。

```bash
# 查看容器健康状态
docker compose ps

# 查看健康检查日志
docker inspect --format='{{json .State.Health}}' <container_id>
```

### 5.2 Sentry 错误追踪配置

```bash
# 在 deploy/.env 中配置
SENTRY_DSN=https://xxxxx@xxxxx.ingest.sentry.io/xxxxx
ENVIRONMENT=production
```

Sentry 集成特性（`backend/app/observability.py`）：

- 自动捕获 FastAPI 异常
- 请求上下文（用户 ID、请求路径等）
- 采样率 10%（`traces_sample_rate=0.1`）
- DSN 为空时完全跳过，零依赖

### 5.3 日志收集

**Docker 内置日志驱动：**

```bash
# 查看所有服务日志
docker compose logs -f

# 查看特定服务最近 100 行
docker compose logs --tail=100 backend

# 带时间戳
docker compose logs -t backend

# 日志驱动配置（docker-compose.yml 中添加）
# logging:
#   driver: json-file
#   options:
#     max-size: "10m"
#     max-file: "3"
```

**日志位置：**

| 日志类型 | 位置 |
|----------|------|
| 后端应用日志 | `docker compose logs backend` |
| Worker 任务日志 | `docker compose logs worker` |
| 前端 Nginx 日志 | `docker compose logs frontend` |
| 数据库日志 | `docker compose logs db` |
| 备份日志 | `/var/log/aiquiz-backup.log` |

**配置日志轮转（宿主机）：**

```bash
# /etc/logrotate.d/aiquiz
/var/log/aiquiz-backup.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
```

---

## 6. 故障排查

### 6.1 常见问题

#### 问题 1：启动失败 — JWT_SECRET_KEY 未配置或太弱

**症状：** backend 容器不断重启，日志显示 `ValueError: JWT_SECRET_KEY 未配置或为空`

**解决：**

```bash
# 查看错误日志
docker compose logs backend | grep JWT_SECRET_KEY

# 生成强密钥
python3 -c "import secrets; print(secrets.token_hex(32))"

# 更新 .env 中的 JWT_SECRET_KEY
nano deploy/.env

# 重启
docker compose down && docker compose up -d --build
```

#### 问题 2：数据库连接失败

**症状：** backend 日志显示 `could not connect to server: Connection refused`

**排查：**

```bash
# 1. 检查 db 容器是否健康
docker compose ps db

# 2. 手动连接测试
docker compose exec db pg_isready -U postgres

# 3. 检查 PostgreSQL 日志
docker compose logs db

# 4. 确认 POSTGRES_PASSWORD 一致
grep POSTGRES_PASSWORD deploy/.env
```

#### 问题 3：AI API 超时

**症状：** Worker 日志显示 MiniMax API 调用超时

**排查：**

```bash
# 1. 检查网络连通性
docker compose exec worker curl -I https://api.minimax.chat

# 2. 检查 API Key 是否有效
echo $MINIMAX_API_KEY

# 3. 查看 worker 任务状态
docker compose logs worker | grep timeout
```

#### 问题 4：前端页面空白

**症状：** 访问 `http://localhost:3000` 显示空白页

**排查：**

```bash
# 1. 检查 frontend 容器状态
docker compose ps frontend

# 2. 查看 Nginx 配置是否正确加载
docker compose exec frontend nginx -t

# 3. 检查前端构建产物是否存在
docker compose exec frontend ls -la /usr/share/nginx/html/

# 4. 重新构建前端
docker compose build --no-cache frontend
```

### 6.2 日志查看速查

```bash
# 实时查看所有服务日志
docker compose logs -f

# 只看错误
docker compose logs backend 2>&1 | grep -i error

# 最近 5 分钟日志
docker compose logs --since 5m

# 导出日志到文件
docker compose logs > /tmp/aiquiz-$(date +%Y%m%d).log
```

### 6.3 紧急回滚流程

```bash
# 1. 停止当前版本
docker compose down

# 2. 回退到上一个 Git 版本
cd /opt/AIsystem
git log --oneline -5  # 确认目标版本
git checkout <previous_commit_hash>

# 3. 如果有数据库迁移回退
cd /opt/AIsystem/deploy
docker compose up -d db redis
sleep 5
docker compose exec backend alembic downgrade -1

# 4. 重新启动所有服务
docker compose up -d --build

# 5. 验证服务
curl http://localhost:8000/health
```

---

## 7. 安全清单

### 7.1 JWT 密钥强度要求

- **最小长度**：32 字符（256 bit 熵）
- **生成方式**：`python3 -c "import secrets; print(secrets.token_hex(32))"`
- **禁止**：任何出现在 `WEAK_JWT_SECRETS` 黑名单中的值（`backend/app/config.py`）
- **定期轮换**：每 90 天或怀疑泄露时立即轮换

### 7.2 CORS 配置

```bash
# 生产环境必须显式配置，禁止使用通配符
# deploy/.env 中设置：
CORS_ORIGINS=["https://aiquiz.example.com"]

# 注意：使用 HTTPS，不要包含 http://localhost
```

### 7.3 防火墙端口

| 端口 | 服务 | 开放范围 |
|------|------|----------|
| 80 | HTTP（跳转 HTTPS） | 公网 |
| 443 | HTTPS | 公网 |
| 22 | SSH | 仅管理 IP |
| 8000 | Backend API | **不开放公网**，仅 localhost/Nginx 反向代理 |
| 3000 | Frontend Nginx | **不开放公网**，仅 localhost/Nginx 反向代理 |
| 5432 | PostgreSQL | **不开放公网**，仅 localhost |
| 6379 | Redis | **不开放公网**，仅 localhost |

```bash
# UFW 防火墙配置示例
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow from <管理IP> to any port 22
sudo ufw enable
```

### 7.4 定期更新依赖

```bash
# 每月检查安全更新
cd /opt/AIsystem

# 更新 Docker 基础镜像
docker compose pull

# 更新 Python 依赖
cd backend
pip install --upgrade -r requirements.txt
pip list --outdated

# 更新 Node.js 依赖
cd ../frontend
npm audit
npm update

# 重新部署
cd /opt/AIsystem/deploy
docker compose down && docker compose up -d --build
```

### 7.5 其他安全措施

- **Docker 安全**：所有容器以非 root 用户运行（`USER appuser`）
- **安全响应头**：HSTS、X-Frame-Options、X-Content-Type-Options 已配置
- **Cookie 安全**：生产环境自动启用 `Secure` 标志（`COOKIE_SECURE`）
- **API 文档**：生产环境默认禁用（`ENABLE_DOCS=false`）
- **密码存储**：使用 bcrypt 哈希，passlib 管理

---

## 附录 A：目录结构

```
/opt/AIsystem/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── config.py         # 应用配置（pydantic Settings）
│   │   ├── main.py           # FastAPI 入口
│   │   ├── database.py       # SQLAlchemy 数据库连接
│   │   ├── observability.py  # 日志 + Sentry
│   │   ├── worker.py         # ARQ 任务队列
│   │   ├── routers/          # API 路由
│   │   ├── models/           # ORM 模型
│   │   └── services/         # 业务逻辑
│   ├── alembic/              # 数据库迁移
│   ├── Dockerfile            # 多阶段构建
│   └── requirements.txt      # Python 依赖
├── frontend/                 # Vue 3 前端
│   ├── src/                  # 源码
│   ├── nginx.conf            # Nginx 配置
│   ├── Dockerfile            # 多阶段构建
│   └── package.json          # Node 依赖
├── deploy/                   # 部署配置
│   ├── docker-compose.yml    # Docker Compose 配置
│   ├── backup.sh             # 数据库备份脚本
│   └── .env                  # 环境变量（不提交到 Git）
└── docs/                     # 文档
    └── deployment-guide.md   # 本文档
```

## 附录 B：常用运维命令速查

```bash
# ===== 启动/停止 =====
cd /opt/AIsystem/deploy
docker compose up -d --build    # 构建并启动
docker compose stop             # 停止
docker compose down             # 停止并删除容器
docker compose down -v          # 停止并删除容器+数据卷（危险！）

# ===== 查看状态 =====
docker compose ps               # 容器状态
docker compose top              # 进程列表
docker stats                    # 资源使用

# ===== 日志 =====
docker compose logs -f          # 实时日志
docker compose logs --tail=100  # 最近 100 行

# ===== 进入容器 =====
docker compose exec backend bash
docker compose exec db psql -U postgres exam_system

# ===== 清理 =====
docker system prune -a          # 清理未使用镜像/网络/构建缓存
docker volume ls -q | xargs docker volume rm  # 删除未使用卷（危险！）
```

---

> **维护者**：DevOps Team  
> **最后更新**：2026-03-15  
> **文档版本**：v1.0
