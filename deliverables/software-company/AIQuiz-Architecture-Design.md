# 智题 AIQuiz — 系统架构设计文档

> **版本**：v1.0  
> **日期**：2026-09-08  
> **作者**：Software Architect (Bob)  
> **状态**：Draft → Review  
> **语言**：中文  
> **输入**：`AIQuiz-PRD.md` v1.0 + 现有代码库分析

---

## 目录

1. [技术选型确认与优化建议](#1-技术选型确认与优化建议)
2. [系统架构设计](#2-系统架构设计)
3. [数据模型审查](#3-数据模型审查)
4. [接口设计审查](#4-接口设计审查)
5. [任务分解（开发计划）](#5-任务分解开发计划)
6. [风险评估与缓解](#6-风险评估与缓解)
7. [里程碑与验收标准](#7-里程碑与验收标准)
8. [附录：关键代码路径](#8-附录关键代码路径)

---

## 1. 技术选型确认与优化建议

### 1.1 当前技术栈评估

| 层级 | 技术 | 版本 | 评估 | 建议 |
|---|---|---|---|---|
| **后端框架** | FastAPI | 0.109.0 | ✅ 合理，异步生态完善 | 升级至 0.115+（安全补丁） |
| **ORM** | SQLAlchemy | 2.0.25 | ✅ 合理，异步支持好 | 保持 |
| **数据库** | PostgreSQL 15 | - | ✅ 生产级，JSON 支持好 | 保持 |
| **缓存/队列** | Redis 7 | - | ✅ 合理 | 保持 |
| **任务队列** | ARQ | ≥0.26.0 | ✅ 已替代裸 threading | 保持 |
| **认证** | python-jose + passlib | - | ⚠️ 双 JWT 库冗余 | 统一为 python-jose |
| **前端框架** | Vue 3 | ^3.3.8 | ✅ 合理 | 升级至 3.5+（性能提升） |
| **UI 库** | Element Plus | ^2.4.0 | ✅ 国内主流 | 保持 |
| **状态管理** | Pinia | ^2.1.7 | ✅ 合理 | 保持 |
| **HTTP 客户端** | Axios | ^1.6.0 | ✅ 合理 | 保持 |
| **构建工具** | Vite | ^5.0.0 | ✅ 合理 | 保持 |
| **部署** | Docker Compose | 3.8 | ✅ 单机构够用 | 保持 |

### 1.2 版本锁定建议

```txt
# requirements.txt 优化
fastapi==0.115.0              # 升级：安全补丁 + 性能
uvicorn[standard]==0.30.0
sqlalchemy==2.0.35            # 升级：bug 修复
psycopg2-binary==2.9.9
bcrypt==4.2.0                 # 升级
passlib==1.7.4
python-dotenv==1.0.1
pydantic==2.6.0               # 升级
pydantic-settings==2.2.0      # 升级
email-validator==2.1.0.post1
asyncpg==0.29.0
python-jose[cryptography]==3.3.0
python-multipart>=0.0.18
httpx==0.27.0
python-docx==1.1.2            # 升级
reportlab==4.1.0              # 升级
pypdf>=4.0.0
redis>=5.0.0                  # 升级
arq==0.26.0
sentry-sdk[fastapi]==2.0.0
alembic==1.13.0
pytest==8.1.0                 # 升级
pytest-asyncio==0.23.0
```

```json
// package.json 关键依赖优化
{
  "dependencies": {
    "axios": "^1.7.0",
    "echarts": "^5.5.0",
    "element-plus": "^2.7.0",
    "pinia": "^2.2.0",
    "vue": "^3.5.0",
    "vue-router": "^4.3.0"
  }
}
```

### 1.3 依赖优化建议

1. **移除 pyjwt 冗余**：当前同时存在 `pyjwt==2.8.0` 和 `python-jose[cryptography]==3.3.0`，统一使用 python-jose（已支持 JWT 标准声明 iss/aud/iat/jti）
2. **添加 python-multipart 显式声明**：文件上传必需
3. **添加 httpx 连接池配置**：AI 调用场景复用连接
4. **前端添加 @types/node**：TypeScript 类型支持

---

## 2. 系统架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户浏览器                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Vue 3 SPA (Element Plus)                         │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │ AI出题   │ │ 智能组卷 │ │ 题库管理 │ │ 试题审核 │ │ 在线考试 │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────────┐  │   │
│  │  │ 知识库   │ │ 模板市场 │ │ 用户权限 │ │ 系统设置             │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                              httpOnly Cookie                                │
│                              (JWT + SameSite)                               │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │ HTTPS
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Nginx (反向代理)                                │
│                     SSL 终止 / 静态资源 / 限流                               │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
              ▼                      ▼                      ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│   FastAPI Backend   │ │   ARQ Worker        │ │   Frontend Static   │
│   (API Server)      │ │   (Task Queue)      │ │   (Nginx Serve)     │
│                     │ │                     │ │                     │
│  ┌───────────────┐  │ │  ┌───────────────┐  │ │  ┌───────────────┐  │
│  │ Auth Router   │  │ │  │ AI Generation │  │ │  │ Vue App       │  │
│  │ Questions     │  │ │  │ Task Runner   │  │ │  │ (SPA Bundle)  │  │
│  │ Papers        │  │ │  └───────────────┘  │ │  └───────────────┘  │
│  │ Exams         │  │ │                     │ │                     │
│  │ Knowledge     │  │ └──────────┬──────────┘ │                     │
│  │ Audit         │  │            │            │                     │
│  │ System        │  │            │            │                     │
│  └───────────────┘  │            │            │                     │
│                     │            │            │                     │
└─────────┬───────────┘            │            └─────────────────────┘
          │                        │
          ▼                        ▼
┌─────────────────────┐ ┌─────────────────────┐
│   PostgreSQL 15     │ │   Redis 7           │
│                     │ │                     │
│  ┌───────────────┐  │ │  ┌───────────────┐  │
│  │ Users         │  │ │  │ Session Cache │  │
│  │ Questions     │  │ │  │ Rate Limiting │  │
│  │ Papers        │  │ │  │ Task Queue    │  │
│  │ Exams         │  │ │  │ Cancel Flags  │  │
│  │ Knowledge     │  │ │  └───────────────┘  │
│  │ AuditLogs     │  │ │                     │
│  └───────────────┘  │ └─────────────────────┘
│                     │
└─────────────────────┘
          │
          ▼
┌─────────────────────┐
│   AI Provider       │
│   (MiniMax/OpenAI)  │
│   - AI 出题         │
│   - 知识点提取      │
│   - 题目质量校验    │
└─────────────────────┘
```

### 2.2 模块划分与交互关系

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Gateway Layer                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │  Auth   │ │ Security│ │  CORS   │ │ Response│ │ Headers │   │
│  │  Router │ │ Headers │ │ Handler │ │ Wrapper │ │ Middle  │   │
│  └────┬────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
│       │                                                          │
├───────┼──────────────────────────────────────────────────────────┤
│       │                    Business Layer                         │
│       │  ┌──────────────────────────────────────────────────┐   │
│       └──│              Service Layer                         │   │
│          │  ┌────────────┐ ┌────────────┐ ┌────────────┐    │   │
│          │  │AuthService │ │AIQuestion  │ │PaperGen    │    │   │
│          │  │            │ │Service     │ │Service     │    │   │
│          │  └────────────┘ └────────────┘ └────────────┘    │   │
│          │  ┌────────────┐ ┌────────────┐ ┌────────────┐    │   │
│          │  │AIProvider  │ │HybridGen   │ │Knowledge   │    │   │
│          │  │Service     │ │Service     │ │Extractor   │    │   │
│          │  └────────────┘ └────────────┘ └────────────┘    │   │
│          │  ┌────────────┐ ┌────────────┐ ┌────────────┐    │   │
│          │  │DocParser   │ │TextChunker │ │Settings    │    │   │
│          │  │Service     │ │Service     │ │Service     │    │   │
│          │  └────────────┘ └────────────┘ └────────────┘    │   │
│          └──────────────────────────────────────────────────┘   │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│                        Data Access Layer                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    SQLAlchemy ORM                         │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │   │
│  │  │ User   │ │Question│ │ Paper  │ │ Exam   │ │Knowledge│ │   │
│  │  │ Model  │ │ Model  │ │ Model  │ │ Model  │ │ Model  │ │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.3 部署架构

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Compose Stack                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  nginx (reverse proxy + static files)                    │    │
│  │  - Port 443 → HTTPS                                      │    │
│  │  - Port 80  → redirect to HTTPS                          │    │
│  │  - /api/*    → backend:8000                              │    │
│  │  - /*        → frontend static                           │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ├─────────────────────────────────────────────────────┐    │
│       │                                                      │    │
│       ▼                                                      ▼    │
│  ┌─────────────────┐                              ┌─────────────┐│
│  │  backend (API)  │◄────────────────────────────►│  worker     ││
│  │  - FastAPI      │    Redis Task Queue          │  (ARQ)      ││
│  │  - Uvicicorn    │                              │  - AI Tasks ││
│  │  - 2 workers    │                              │  - 20 max   ││
│  └────────┬────────┘                              └──────┬──────┘│
│           │                                              │       │
│           └──────────────────┬───────────────────────────┘       │
│                              │                                   │
│                    ┌─────────▼─────────┐                        │
│                    │  PostgreSQL 15    │                        │
│                    │  - Port 5432      │                        │
│                    │  - Volume: pgdata │                        │
│                    └───────────────────┘                        │
│                              │                                   │
│                    ┌─────────▼─────────┐                        │
│                    │  Redis 7          │                        │
│                    │  - Port 6379      │                        │
│                    │  - Volume: redis  │                        │
│                    └───────────────────┘                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 数据模型审查

### 3.1 当前模型评估

#### 3.1.1 模型清单

| 模型 | 表名 | 行数 | 评估 | 建议 |
|---|---|---|---|---|
| User | users | 53 | ✅ 合理 | 保持 |
| Subject | subjects | 49 | ✅ 合理 | 保持 |
| Chapter | chapters | 124 | ✅ 合理 | 保持 |
| Question | questions | 385 | ✅ 合理 | 保持 |
| QuestionOption | question_options | 186 | ✅ 合理 | 保持 |
| ExamPaper | exam_papers | 211 | ✅ 合理 | 保持 |
| ExamPaperQuestion | exam_paper_questions | 222 | ✅ 合理 | 保持 |
| ExamRecord | exam_records | 267 | ✅ 合理 | 保持 |
| UserAnswer | user_answers | 288 | ✅ 合理 | 保持 |
| AIPromptTemplate | ai_prompt_templates | 291 | ✅ 合理 | 保持 |
| AICallLog | ai_call_logs | 314 | ✅ 合理 | 保持 |
| GenerationTask | generation_tasks | 337 | ✅ 合理 | 保持 |
| AuditLog | audit_logs | 366 | ✅ 合理 | 保持 |
| KnowledgePoint | knowledge_points | 360 | ✅ 合理 | 保持 |
| KnowledgeBase | knowledge_bases | 657 | ✅ 合理 | 保持 |
| KnowledgeEntry | knowledge_entries | 729 | ✅ 合理 | 保持 |
| PaperTemplate | paper_templates | 429 | ✅ 合理 | 保持 |
| PaperVersion | paper_versions | 419 | ✅ 合理 | 保持 |
| Notification | notifications | - | ✅ 合理 | 保持 |
| SystemSetting | system_settings | - | ✅ 合理 | 保持 |
| PasswordResetRequest | password_reset_requests | - | ✅ 合理 | 保持 |
| ExamCategory | exam_categories | - | ✅ 合理 | 保持 |
| ExamType | exam_types | - | ✅ 合理 | 保持 |

#### 3.1.2 模型问题清单

| 问题 | 位置 | 严重度 | 建议修复 |
|---|---|---|---|
| **User 模型混用 mapped_column 和 Column** | `models/user.py` | 🟡 中 | 统一为 mapped_column（SQLAlchemy 2.0 风格） |
| **Question 缺少全文搜索索引** | `questions.content` | 🟡 中 | 添加 GIN 索引（pg_trgm） |
| **ExamRecord.answers 用 JSON 存储** | `exam_records.answers` | 🟡 中 | 考虑迁移到 UserAnswer 表（已存在） |
| **KnowledgePoint 缺少路径缓存** | `knowledge_points` | 🟢 低 | 添加 path 字段加速树查询 |
| **缺少软删除** | 所有表 | 🟡 中 | 添加 deleted_at 字段 |

### 3.2 需要新增的表

#### 3.2.1 审核通知表（已有 notifications，需确认覆盖）

当前 `notifications` 表已存在，需确认是否覆盖审核通知场景。

#### 3.2.2 AI 服务商配置表（已有 system_settings，需确认）

当前 AI 配置存储在 `system_settings` 表中，建议独立为 `ai_providers` 表：

```sql
CREATE TABLE ai_providers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,           -- 显示名称
    provider_type VARCHAR(30) NOT NULL,  -- openai/minimax/deepseek/...
    api_key_encrypted TEXT NOT NULL,     -- 加密存储
    base_url VARCHAR(255),               -- API 端点
    model VARCHAR(100) NOT NULL,         -- 模型 ID
    config JSONB DEFAULT '{}',           -- 额外配置
    is_default BOOLEAN DEFAULT FALSE,
    status SMALLINT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.3 索引策略

```sql
-- 现有索引（已存在）
CREATE INDEX idx_questions_chapter_id ON questions(chapter_id);
CREATE INDEX idx_questions_subject_id ON questions(subject_id);
CREATE INDEX idx_exam_paper_questions_exam_paper_id ON exam_paper_questions(exam_paper_id);
CREATE INDEX idx_exam_records_user_id ON exam_records(user_id);
CREATE INDEX idx_generation_tasks_status ON generation_tasks(status);

-- 建议新增索引
CREATE INDEX idx_questions_audit_status ON questions(audit_status) WHERE audit_status = 'pending';
CREATE INDEX idx_questions_created_by ON questions(created_by);
CREATE INDEX idx_questions_source ON questions(source);
CREATE INDEX idx_exam_records_exam_paper_id_status ON exam_records(exam_paper_id, status);
CREATE INDEX idx_knowledge_points_parent_id ON knowledge_points(parent_id);
CREATE INDEX idx_knowledge_points_category_id ON knowledge_points(category_id);
CREATE INDEX idx_audit_logs_question_id_created_at ON audit_logs(question_id, created_at DESC);
CREATE INDEX idx_ai_call_logs_created_at ON ai_call_logs(created_at DESC);

-- 全文搜索索引（PostgreSQL）
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_questions_content_trgm ON questions USING gin(content gin_trgm_ops);
```

---

## 4. 接口设计审查

### 4.1 当前 API 清单

| 模块 | 前缀 | 端点数 | 评估 |
|---|---|---|---|
| 认证 | `/api/auth` | 6 | ✅ 合理 |
| 科目 | `/api/subjects` | 4 | ✅ 合理 |
| 章节 | `/api/chapters` | 4 | ✅ 合理 |
| 题目 | `/api/questions` | 12 | ✅ 合理 |
| AI 出题 | `/api/ai` | 8 | ✅ 合理 |
| 试卷 | `/api/papers` | 10 | ✅ 合理 |
| 试卷版本 | `/api/paper-versions` | 5 | ✅ 合理 |
| 考试 | `/api/exams` | 8 | ⚠️ 需补全校验 |
| 考试记录 | `/api/exam-records` | 4 | ✅ 合理 |
| 审核 | `/api/audit` | 6 | ✅ 合理 |
| 仪表盘 | `/api/dashboard` | 4 | ✅ 合理 |
| 知识点 | `/api/knowledge` | 10 | ✅ 合理 |
| 知识库 | `/api/knowledge-bases` | 8 | ✅ 合理 |
| 系统 | `/api/system` | 15 | ✅ 合理 |
| 通知 | `/api/notifications` | 5 | ✅ 合理 |
| 模板 | `/api/paper-templates` | 8 | ✅ 合理 |

**总计：约 117 个 API 端点**

### 4.2 需要新增的接口

| 接口 | 方法 | 路径 | 说明 |
|---|---|---|---|
| 批量审核 | POST | `/api/audit/batch/review` | 批量通过/驳回 |
| 考试分析 | GET | `/api/exams/{id}/analysis` | 试卷难度/区分度/正确率 |
| 题目查重 | POST | `/api/questions/duplicate-check` | 相似度查重 |
| AI 服务商测试 | POST | `/api/system/ai-providers/test` | 测试 AI 连接 |
| 数据备份 | POST | `/api/system/backup` | 手动触发备份 |
| 导入预览 | POST | `/api/questions/preview` | 导入前预览（已有） |
| 导出进度 | GET | `/api/questions/export/progress` | 大导出异步化 |

### 4.3 接口安全设计

#### 4.3.1 认证流程

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Browser │                    │  FastAPI │                    │  Redis   │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                               │                               │
     │  POST /auth/login/json        │                               │
     │  {username, password}         │                               │
     │──────────────────────────────►│                               │
     │                               │                               │
     │                               │  bcrypt.verify()              │
     │                               │  create_access_token()        │
     │                               │                               │
     │  200 OK + Set-Cookie          │                               │
     │  access_token=xxx; HttpOnly   │                               │
     │◄──────────────────────────────│                               │
     │                               │                               │
     │  GET /api/questions           │                               │
     │  Cookie: access_token=xxx     │                               │
     │──────────────────────────────►│                               │
     │                               │                               │
     │                               │  get_current_user()           │
     │                               │  (read cookie → decode JWT)   │
     │                               │                               │
     │  200 OK + data                │                               │
     │◄──────────────────────────────│                               │
     │                               │                               │
```

#### 4.3.2 权限校验层级

```
Level 1: 认证层 (get_current_user)
  └─ 验证 JWT 有效性
  └─ 检查用户状态 (status=1)
  └─ 加载用户基本信息

Level 2: 角色层 (require_role)
  └─ require_admin (role=1)
  └─ require_teacher_or_admin (role=1,2)
  └─ require_student (role=3)

Level 3: 权限层 (require_permission)
  └─ 检查用户 menu_permissions
  └─ 管理员自动通过

Level 4: 资源层 (IDOR 防护)
  └─ 验证资源归属 (created_by == current_user.id)
  └─ 验证考生名单 (student_ids contains current_user.id)
```

#### 4.3.3 限流策略

| 场景 | 限流规则 | 实现方式 |
|---|---|---|
| 登录 | 5 次/30 分钟/用户名 | Redis 计数器 |
| AI 出题 | 10 次/分钟/用户 | Redis 令牌桶 |
| 全局 API | 100 次/分钟/IP | Redis 令牌桶 |
| 文件导入 | 5 次/小时/用户 | Redis 计数器 |

---

## 5. 任务分解（开发计划）

### 5.1 Phase 1：止血（1 周）

**目标**：恢复版本控制、轮换密钥、修复安全漏洞、建立 CI/CD 基线

#### T01：版本控制恢复与密钥轮换

| 项目 | 内容 |
|---|---|
| **任务描述** | 提交所有未提交文件、轮换泄露密钥、建立 .gitignore |
| **涉及文件** | `.gitignore`, `backend/.env`, `deploy/.env`, 所有未跟踪文件 |
| **工作量** | 0.5 人日 |
| **依赖** | 无 |
| **验收标准** | `git status` 干净、CI 全绿、密钥已轮换 |

#### T02：CI/CD 生效与安全加固

| 项目 | 内容 |
|---|---|
| **任务描述** | 修复 CI 流程、cookie secure 配置化、统一认证库 |
| **涉及文件** | `.github/workflows/ci.yml`, `backend/app/routers/auth.py`, `backend/app/services/auth.py`, `backend/requirements.txt` |
| **工作量** | 1 人日 |
| **依赖** | T01 |
| **验收标准** | CI 全绿、cookie secure=not debug、移除 pyjwt |

#### T03：前端认证迁移完成

| 项目 | 内容 |
|---|---|
| **任务描述** | 删除 localStorage XOR token 逻辑、完全依赖 httpOnly cookie |
| **涉及文件** | `frontend/src/stores/auth.js`, `frontend/src/api/index.js` |
| **工作量** | 0.5 人日 |
| **依赖** | T02 |
| **验收标准** | 无 localStorage token 读写、登录/登出正常 |

#### T04：考试模块校验补全

| 项目 | 内容 |
|---|---|
| **任务描述** | 补全 start/submit/create 校验（考生名单、时间窗、题目归属） |
| **涉及文件** | `backend/app/routers/exams.py`, `backend/app/schemas/exam.py` |
| **工作量** | 1 人日 |
| **依赖** | 无 |
| **验收标准** | 名单外考生无法参考、时间外无法作答、校验失败返回明确错误 |

#### T05：导入安全加固

| 项目 | 内容 |
|---|---|
| **任务描述** | 限制文件大小 10MB、防公式注入、SAVEPOINT 事务 |
| **涉及文件** | `backend/app/routers/questions/import_export.py` |
| **工作量** | 0.5 人日 |
| **依赖** | 无 |
| **验收标准** | 超大文件 413、公式注入被转义、部分失败可回滚 |

### 5.2 Phase 2：重构（2 周）

**目标**：巨型文件拆分、任务队列升级、测试覆盖提升

#### T06：后端巨型文件拆分

| 项目 | 内容 |
|---|---|
| **任务描述** | knowledge.py (1505行) → 子模块、import_export.py (1308行) → 子模块 |
| **涉及文件** | `backend/app/routers/knowledge.py` → `knowledge/` 子目录、`backend/app/routers/questions/import_export.py` → `import_export/` 子目录 |
| **工作量** | 2 人日 |
| **依赖** | Phase 1 完成 |
| **验收标准** | 单文件 < 500 行、所有测试通过、API 行为不变 |

#### T07：前端巨型文件拆分

| 项目 | 内容 |
|---|---|
| **任务描述** | PaperManagementView.vue (1711行) → 子组件、其他 >1000 行组件拆分 |
| **涉及文件** | `frontend/src/views/admin/PaperManagementView.vue` → `paper/` 子目录、`AIQuestionView.vue` → `ai/` 子目录、`UserPermissionView.vue` → `user/` 子目录、`AutoPaperView.vue` → `auto-paper/` 子目录、`SystemSettingsView.vue` → `settings/` 子目录 |
| **工作量** | 3 人日 |
| **依赖** | Phase 1 完成 |
| **验收标准** | 单组件 < 500 行、页面功能不变、构建成功 |

#### T08：异步任务队列升级验证

| 项目 | 内容 |
|---|---|
| **任务描述** | 验证 ARQ worker 正常运行、悬挂任务回收、取消机制 |
| **涉及文件** | `backend/app/worker.py`, `backend/app/routers/ai_templates/task_runner.py` |
| **工作量** | 1 人日 |
| **依赖** | Phase 1 完成 |
| **验收标准** | Worker 正常消费任务、重启后悬挂任务置为 failed、取消机制生效 |

#### T09：测试覆盖率提升

| 项目 | 内容 |
|---|---|
| **任务描述** | 核心链路测试补充（认证、出题、组卷、考试、审核） |
| **涉及文件** | `backend/tests/unit/test_p0_regressions.py`, `backend/tests/unit/test_auth_security.py`, `backend/tests/unit/test_ai_question.py`, `backend/tests/unit/test_hybrid_generator.py`, `backend/tests/unit/test_security_fixes.py`, `backend/tests/unit/test_commercial_foundation.py`, `backend/tests/unit/test_license.py`, `backend/tests/unit/test_student_exam_audit.py`, `backend/tests/test_knowledge_base_e2e.py` |
| **工作量** | 3 人日 |
| **依赖** | T06 |
| **验收标准** | 核心链路覆盖率 ≥ 50%、CI 全绿 |

### 5.3 Phase 3：加固（1 周）

**目标**：IDOR 修复、权限统一、性能优化

#### T10：IDOR 全面修复

| 项目 | 内容 |
|---|---|
| **任务描述** | 任务/考试/试卷/知识库资源归属校验 |
| **涉及文件** | `backend/app/routers/exams.py`, `backend/app/routers/papers.py`, `backend/app/routers/knowledge.py`, `backend/app/routers/ai_templates/*.py` |
| **工作量** | 1.5 人日 |
| **依赖** | Phase 2 完成 |
| **验收标准** | 跨用户访问返回 403/404、测试覆盖 |

#### T11：权限体系统一

| 项目 | 内容 |
|---|---|
| **任务描述** | 后端下发权限、前端不再维护默认表 |
| **涉及文件** | `backend/app/models/user.py`, `backend/app/routers/auth.py`, `frontend/src/stores/auth.js`, `frontend/src/router/index.js` |
| **工作量** | 1 人日 |
| **依赖** | T10 |
| **验收标准** | 前端无角色默认权限表、权限变更实时生效 |

#### T12：前端性能优化

| 项目 | 内容 |
|---|---|
| **任务描述** | 虚拟滚动、搜索防抖、批量接口优化 |
| **涉及文件** | `frontend/src/views/admin/QuestionBankView.vue`, `frontend/src/views/admin/PaperManagementView.vue`, `frontend/src/composables/*.ts` |
| **工作量** | 1.5 人日 |
| **依赖** | T07 |
| **验收标准** | 列表页渲染 < 1s、搜索响应 < 300ms |

### 5.4 Phase 4：验收（1 周）

**目标**：性能优化、文档完善、部署演练

#### T13：性能优化与监控

| 项目 | 内容 |
|---|---|
| **任务描述** | 数据库索引优化、Redis 缓存策略、Sentry 接入 |
| **涉及文件** | `backend/app/database.py`, `backend/app/services/redis_client.py`, `backend/app/observability.py` |
| **工作量** | 1.5 人日 |
| **依赖** | Phase 3 完成 |
| **验收标准** | API P95 < 500ms、缓存命中率 > 80%、错误追踪正常 |

#### T14：文档完善与部署演练

| 项目 | 内容 |
|---|---|
| **任务描述** | 生产环境部署指南、故障排查手册、API 文档完善 |
| **涉及文件** | `README.md`, `CLAUDE.md`, `docs/`, `deploy/` |
| **工作量** | 1 人日 |
| **依赖** | T13 |
| **验收标准** | 新开发者可独立部署、故障排查有文档 |

#### T15：安全扫描与修复

| 项目 | 内容 |
|---|---|
| **任务描述** | OWASP Top 10 扫描、依赖漏洞扫描、修复发现的问题 |
| **涉及文件** | 全仓 |
| **工作量** | 1 人日 |
| **依赖** | T14 |
| **验收标准** | 无高危漏洞、依赖最新安全版本 |

---

## 6. 风险评估与缓解

### 6.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 | 负责人 |
|---|---|---|---|---|
| **AI 服务商 API 变更** | 出题功能不可用 | 中 | 多服务商可切换、OpenAI 兼容协议优先 | 架构师 |
| **AI 生成题目质量不稳定** | 人工审核负担加重 | 高 | 规则模板兜底 + 质量校验 + 人工审核 | 产品经理 |
| **PostgreSQL 性能瓶颈** | 大规模题库查询变慢 | 中 | 索引优化 + 查询下推 + 缓存 | 后端工程师 |
| **Redis 故障** | 限流/缓存失效 | 低 | 优雅降级（限流放行，缓存穿透到 DB） | 后端工程师 |
| **前端巨型文件维护困难** | Bug 修复/功能迭代慢 | 高 | 优先拆分，单文件 < 500 行 | 前端工程师 |
| **异步任务丢失** | 出题/组卷任务中断 | 中 | 引入持久化任务队列（ARQ/RQ） | 后端工程师 |
| **XSS/CSRF 攻击** | 用户数据泄露 | 中 | DOMPurify + SameSite Cookie + 输入过滤 | 前端工程师 |
| **密钥泄露** | AI 调用费用损失 | 低 | 密钥轮换 + 掩码返回 + 访问审计 | 运维 |

### 6.2 实施风险

| 风险 | 影响 | 概率 | 缓解措施 |
|---|---|---|---|
| **巨型文件拆分引入 Bug** | 功能回归 | 高 | 拆分前写测试、灰度发布、回滚方案 |
| **认证迁移导致用户无法登录** | 用户无法访问 | 中 | 渐进迁移、保留兼容期、充分测试 |
| **测试覆盖率不足** | 回归风险高 | 高 | 核心链路优先、CI 门禁 |
| **CI 流程不稳定** | 开发效率降低 | 中 | 分步验证、缓存依赖、并行执行 |
| **数据库迁移失败** | 服务不可用 | 低 | 备份先行、回滚脚本、低峰期执行 |

### 6.3 资源风险

| 风险 | 影响 | 概率 | 缓解措施 |
|---|---|---|---|
| **开发人力不足（1-2 人）** | 迭代速度受限 | 高 | 聚焦核心功能、P0 优先、自动化工具 |
| **AI 调用成本超支** | 运营成本增加 | 中 | 设置上限与告警、规则模板兜底 |
| **缺少预发布环境** | 生产问题难提前发现 | 中 | Docker Compose 本地模拟、灰度发布 |

---

## 7. 里程碑与验收标准

### 7.1 里程碑总览

```
Week 1        Week 2-3       Week 4        Week 5
  │             │             │             │
  ▼             ▼             ▼             ▼
┌─────┐     ┌─────┐     ┌─────┐     ┌─────┐
│Phase│     │Phase│     │Phase│     │Phase│
│  1  │────►│  2  │────►│  3  │────►│  4  │
│止血 │     │重构 │     │加固 │     │验收 │
└─────┘     └─────┘     └─────┘     └─────┘
  │             │             │             │
  ▼             ▼             ▼             ▼
基线恢复     代码质量      性能达标      生产就绪
CI 全绿     测试覆盖      安全通过      文档完善
```

### 7.2 各 Phase 验收标准

#### Phase 1：止血（Week 1）

| 验收项 | 标准 | 验证方式 |
|---|---|---|
| 版本控制恢复 | `git status` 干净、所有文件已提交 | `git status` |
| 密钥轮换 | 泄露 Key 已失效、新 Key 生效 | MiniMax 控制台验证 |
| CI/CD 生效 | CI 全绿（ruff + pytest + typecheck） | GitHub Actions |
| Cookie 安全 | `secure=not debug`、生产 HTTPS 下安全 | 浏览器 DevTools |
| 前端认证迁移 | 无 localStorage token、完全依赖 cookie | 代码审查 + 功能测试 |
| 考试校验 | 名单外/时间外无法作答 | 集成测试 |
| 导入安全 | 超大文件 413、公式注入被转义 | 集成测试 |

#### Phase 2：重构（Week 2-3）

| 验收项 | 标准 | 验证方式 |
|---|---|---|
| 后端文件拆分 | 单文件 < 500 行 | `wc -l` |
| 前端组件拆分 | 单组件 < 500 行 | `wc -l` |
| 任务队列 | Worker 正常消费、悬挂任务回收 | 功能测试 |
| 测试覆盖 | 核心链路覆盖率 ≥ 50% | `pytest --cov` |
| 功能回归 | 所有现有功能正常 | 回归测试 |

#### Phase 3：加固（Week 4）

| 验收项 | 标准 | 验证方式 |
|---|---|---|
| IDOR 修复 | 跨用户访问返回 403/404 | 安全测试 |
| 权限统一 | 前端无角色默认权限表 | 代码审查 |
| 前端性能 | 列表页渲染 < 1s | Lighthouse |
| API 性能 | P95 < 500ms | 压测 |

#### Phase 4：验收（Week 5）

| 验收项 | 标准 | 验证方式 |
|---|---|---|
| 安全扫描 | 无高危漏洞 | OWASP ZAP |
| 部署演练 | 新开发者可独立部署 | 文档验证 |
| 监控告警 | Sentry 正常、错误可追溯 | 触发测试错误 |
| 文档完善 | 部署指南、故障排查手册齐全 | 文档审查 |

### 7.3 最终交付物清单

| 交付物 | 说明 |
|---|---|
| 可运行系统 | Docker Compose 一键启动 |
| CI/CD 流水线 | GitHub Actions 自动检查 |
| 测试套件 | 核心链路覆盖率 ≥ 50% |
| 部署文档 | 生产环境部署指南 |
| API 文档 | Swagger/ReDoc 自动生成 |
| 故障排查手册 | 常见问题与解决方案 |
| 安全报告 | OWASP 扫描结果 |

---

## 8. 附录：关键代码路径

### 8.1 认证流程关键路径

```
登录：
  frontend/src/stores/auth.js::login()
    → frontend/src/api/index.js::authAPI.login()
      → POST /api/auth/login/json
        → backend/app/routers/auth.py::login_json()
          → bcrypt.verify()
          → AuthService.create_access_token()
          → _set_auth_cookie() [设置 httpOnly cookie]
    ← 200 OK + Set-Cookie

请求拦截：
  frontend/src/api/index.js::api.interceptors.response.use()
    → 401 且非认证端点 → POST /api/auth/refresh
    → 刷新成功 → 重放原请求
    → 刷新失败 → 跳转登录页

认证中间件：
  backend/app/utils/security.py::get_current_user()
    → 读取 cookie "access_token"
    → 兼容 Authorization 头
    → AuthService.decode_token()
    → 查询用户 → 检查 status
    → 返回 User 对象
```

### 8.2 AI 出题流程关键路径

```
异步出题：
  POST /api/ai/hybrid-generate-async
    → backend/app/routers/ai_templates/crud.py
      → 创建 GenerationTask 记录
      → 调用 ARQ: run_generation_task.enqueue(task_id, req_dict, user_id)
    ← 202 Accepted + task_id

Worker 执行：
  backend/app/worker.py::run_generation_task()
    → asyncio.to_thread(execute_generation_task)
      → backend/app/routers/ai_templates/task_runner.py
        → 规则引擎分类知识点
        → 构建出题策略
        → 调用 AI Provider 生成题目
        → 质量校验
        → 写入数据库
        → 更新任务进度

进度查询：
  GET /api/ai/task/{task_id}/progress
    → 查询 GenerationTask 表
    ← {status, progress, result, error_message}

取消任务：
  POST /api/ai/task/{task_id}/cancel
    → set_cancel_flag(task_id) [Redis]
    → Worker 检查点轮询 → 提前终止
```

### 8.3 考试流程关键路径

```
创建考试：
  POST /api/exams/
    → 验证教师/管理员权限
    → 创建 ExamPaper + ExamRecord
    → 配置考生名单、时间窗

考生参考：
  POST /api/exams/{id}/start
    → _check_exam_access() [名单+时间校验]
    → 创建 ExamRecord
    ← 试卷内容（不含答案）

作答保存：
  POST /api/exams/{id}/save-answer
    → 验证考试状态
    → 保存 UserAnswer

交卷：
  POST /api/exams/{id}/submit
    → 客观题自动判分
    → 计算总分
    → 更新 ExamRecord.status = "submitted"
    ← 客观题成绩
```

### 8.4 导入导出关键路径

```
导入：
  POST /api/questions/import
    → 文件大小校验 (≤10MB)
    → 文件格式检测 (魔数)
    → 解析题目 (Excel/Word)
    → 去重 (内容+题型)
    → 批量插入 (SAVEPOINT 事务)
    ← ImportResult {success_count, fail_count, errors}

导出：
  GET /api/questions/export?format=excel|word|pdf
    → 查询题目
    → 生成文件 (openpyxl/python-docx/reportlab)
    → 防公式注入 (_safe_cell_value)
    ← StreamingResponse (blob)
```

---

## 附录 A：数据库迁移脚本

```sql
-- 新增索引
CREATE INDEX CONCURRENTLY idx_questions_audit_status ON questions(audit_status) WHERE audit_status = 'pending';
CREATE INDEX CONCURRENTLY idx_questions_created_by ON questions(created_by);
CREATE INDEX CONCURRENTLY idx_questions_source ON questions(source);
CREATE INDEX CONCURRENTLY idx_exam_records_exam_paper_id_status ON exam_records(exam_paper_id, status);
CREATE INDEX CONCURRENTLY idx_knowledge_points_parent_id ON knowledge_points(parent_id);
CREATE INDEX CONCURRENTLY idx_knowledge_points_category_id ON knowledge_points(category_id);
CREATE INDEX CONCURRENTLY idx_audit_logs_question_id_created_at ON audit_logs(question_id, created_at DESC);
CREATE INDEX CONCURRENTLY idx_ai_call_logs_created_at ON ai_call_logs(created_at DESC);

-- 全文搜索
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX CONCURRENTLY idx_questions_content_trgm ON questions USING gin(content gin_trgm_ops);

-- 软删除字段（可选）
ALTER TABLE questions ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE exam_papers ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE knowledge_points ADD COLUMN deleted_at TIMESTAMPTZ;
```

## 附录 B：环境变量清单

```bash
# 应用
APP_NAME=AIQuiz
DEBUG=false
ENVIRONMENT=production

# 数据库
DATABASE_URL=postgresql://postgres:password@db:5432/exam_system

# JWT
JWT_SECRET_KEY=<generate-with-secrets.token-hex-32>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis
REDIS_URL=redis://redis:6379/0

# CORS
CORS_ORIGINS=["https://your-domain.com"]

# AI
MINIMAX_API_KEY=<your-minimax-key>

# 可选
SENTRY_DSN=<your-sentry-dsn>
PDF_FONT_PATH=/usr/share/fonts/truetype/wqy/wqy-microhei.ttc
```

---

> **文档状态**：Draft → 待 Review  
> **下一步**：提交给 Team Lead 汇总，与 Engineer 对齐实施细节。
