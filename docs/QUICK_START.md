# 快速入门指南

> 本指南帮助你在 **10 分钟内** 完成项目的本地搭建并运行第一次 AI Agent 对话。

---

## 目录

1. [环境要求](#1-环境要求)
2. [获取代码](#2-获取代码)
3. [方式一：Docker Compose 一键启动（推荐）](#3-方式一docker-compose-一键启动推荐)
4. [方式二：本地开发模式](#4-方式二本地开发模式)
5. [配置环境变量](#5-配置环境变量)
6. [启动前端](#6-启动前端)
7. [验证服务](#7-验证服务)
8. [第一次对话](#8-第一次对话)
9. [核心功能速览](#9-核心功能速览)
10. [四种 Agent 模式](#10-四种-agent-模式)
11. [常用 Makefile 命令](#11-常用-makefile-命令)
12. [常见问题](#12-常见问题)
13. [下一步](#13-下一步)

---

## 1. 环境要求

| 工具                            | 版本要求                | 用途            |
| ------------------------------- | ----------------------- | --------------- |
| **Python**                      | 3.13+                   | 后端运行时      |
| **uv**                          | 最新版                  | Python 包管理器 |
| **Node.js**                     | 18+                     | 前端开发        |
| **PostgreSQL**                  | 16+（含 pgvector 扩展） | 数据库          |
| **Docker** + **Docker Compose** | 最新版（可选，推荐）    | 容器化部署      |

> **提示**：使用 Docker Compose 可跳过手动安装 PostgreSQL 和 Qdrant 的步骤。

---

## 2. 获取代码

```bash
git clone <repository-url>
cd fastapi-langgraph-agent-production-ready-template
```

---

## 3. 方式一：Docker Compose 一键启动（推荐）

这是最简单的启动方式，自动创建所有依赖服务（PostgreSQL、Qdrant、Prometheus、Grafana 等）。

### 3.1 准备环境变量文件

```bash
cp .env.example .env
```

编辑 `.env`，**至少填写以下必填项**：

```bash
# 必填：你的 OpenAI API Key（或兼容 API 的 Key）
OPENAI_API_KEY=sk-your-api-key-here

# 必填：JWT 密钥（随机字符串，用于用户认证）
JWT_SECRET_KEY=your-random-secret-key-here

# 数据库配置（Docker 内部使用，保持默认即可）
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=mydb
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
```

> **可选配置**：如需使用自定义 OpenAI 兼容 API（如 Azure OpenAI、DeepSeek 等），在 `.env` 中设置 `OPENAI_API_BASE`：
> ```bash
> OPENAI_API_BASE=https://your-api-base-url/v1
> ```

### 3.2 启动全部服务

```bash
# 构建并启动全部服务（后端 + 数据库 + Qdrant + 前端 + 监控）
docker compose up -d
```

### 3.3 按需启动（本地开发推荐）

项目拆分为三个 Compose 文件，可按需组合：

| 文件 | 包含服务 | 用途 |
|------|----------|------|
| `docker-compose-base.yml` | PostgreSQL + Qdrant | 基础设施（本地开发必备） |
| `docker-compose-monitoring.yml` | Prometheus + Grafana + cAdvisor | 监控栈（可选） |
| `docker-compose.yml` | 后端 API + 前端 + include 以上两者 | 完整部署 |

**常用启动组合：**

```bash
# ① 仅数据库 + Qdrant（最轻量，本地开发后端/前端时使用）
docker compose -f docker-compose-base.yml up -d

# ② 数据库 + Qdrant + 监控（需要 Grafana 看指标时）
docker compose -f docker-compose-base.yml -f docker-compose-monitoring.yml up -d

# ③ 单独启动某个服务（例如只启动 Qdrant）
docker compose -f docker-compose-base.yml up -d qdrant

# ④ 单独启动 PostgreSQL
docker compose -f docker-compose-base.yml up -d db

# ⑤ 全部服务（后端 + 前端 + 数据库 + Qdrant + 监控）
docker compose up -d
```

**单独停止某个服务：**

```bash
# 停止后端容器（保留数据库和 Qdrant 运行）
docker compose stop app

# 停止前端容器
docker compose stop frontend

# 停止 Grafana
docker compose -f docker-compose-base.yml -f docker-compose-monitoring.yml stop grafana
```

> **本地开发典型流程**：先用 ① 启动数据库和 Qdrant，然后本地运行后端（`make dev` 或 `python run.py`）和前端（`npm run dev`），实现热重载开发。

### 3.4 服务端口一览

| 服务             | 地址                       | 说明                        |
| ---------------- | -------------------------- | --------------------------- |
| **后端 API**     | http://localhost:8000      | FastAPI 应用                |
| **Swagger 文档** | http://localhost:8000/docs | API 交互式文档              |
| **前端 UI**      | http://localhost:3001      | React 聊天界面              |
| **Prometheus**   | http://localhost:9090      | 指标监控                    |
| **Grafana**      | http://localhost:3000      | 可视化仪表盘（admin/admin） |
| **Qdrant**       | http://localhost:6333      | 向量数据库                  |

### 3.5 停止服务

```bash
# 停止全部服务并移除容器
docker compose down

# 仅停止基础设施
docker compose -f docker-compose-base.yml down

# 停止基础设施 + 监控
docker compose -f docker-compose-base.yml -f docker-compose-monitoring.yml down

# 停止并清除数据卷（⚠️ 会删除数据库数据）
docker compose down -v
```

---

## 4. 方式二：本地开发模式

适合需要频繁修改代码、热重载调试的场景。

### 4.1 安装 Python 依赖

```bash
# 安装 uv（如未安装）
pip install uv

# 安装项目依赖
uv sync
```

### 4.2 准备数据库

**选项 A：使用 Docker 启动 PostgreSQL + Qdrant**

```bash
# 仅启动数据库和 Qdrant（不启动后端应用）
make docker-run-env ENV=development
```

> 注意：此方式下后端会尝试同时启动，你可以先 `docker compose stop app` 停止后端容器，然后用本地方式运行。

**选项 B：使用已有的 PostgreSQL**

确保你的 PostgreSQL 安装了 `pgvector` 扩展，然后在 `.env` 中配置连接信息：

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mydb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

手动初始化数据库表（可选，ORM 会自动创建）：

```bash
psql -h localhost -U postgres -d mydb -f schema.sql
```

### 4.3 准备环境变量

```bash
cp .env.example .env
```

编辑 `.env`，**确保填写**：
- `OPENAI_API_KEY` — LLM API 密钥
- `JWT_SECRET_KEY` — JWT 认证密钥
- `POSTGRES_HOST=localhost` — 如果数据库运行在本地

### 4.4 启动后端

```bash
# 开发模式（支持热重载）
make dev
```

> **Windows 用户**：如果 `make dev` 遇到 `uvloop` 相关错误（uvloop 不支持 Windows），请使用：
> ```bash
> python run.py
> ```

后端启动后访问：
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/v1/health

---

## 5. 配置环境变量

以下是 `.env` 中的完整配置说明：

### 必填配置

```bash
# LLM API 密钥
OPENAI_API_KEY=sk-your-key

# JWT 认证密钥
JWT_SECRET_KEY=your-secret-key

# 数据库连接
POSTGRES_HOST=db          # Docker 中用 db，本地用 localhost
POSTGRES_PORT=5432
POSTGRES_DB=mydb
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword
```

### 可选配置

```bash
# 自定义 LLM API 地址（兼容 OpenAI 接口）
OPENAI_API_BASE=https://your-api-base/v1

# 默认模型
DEFAULT_LLM_MODEL=gpt-4o-mini

# Langfuse 可观测性（可选，不配置不影响使用）
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_HOST=https://cloud.langfuse.com

# Qdrant（RAG 知识库检索）
QDRANT_HOST=qdrant        # Docker 中用 qdrant，本地用 localhost
QDRANT_PORT=6333

# 长期记忆模型
LONG_TERM_MEMORY_MODEL=gpt-4o-mini
LONG_TERM_MEMORY_EMBEDDER_MODEL=text-embedding-3-small
LONG_TERM_MEMORY_EMBEDDER_BASE_URL=   # 自定义 Embedding 端点（留空=使用 OpenAI）
LONG_TERM_MEMORY_EMBEDDER_DIMS=1536   # 768 适用于 bge-base-zh-v1.5，1536 适用于 OpenAI

# 对话摘要（自动压缩过长的对话历史）
SUMMARIZATION_MODEL=gpt-4o-mini       # 用于摘要的模型
SUMMARIZATION_TRIGGER_TOKENS=4000     # 触发摘要的 token 阈值
SUMMARIZATION_KEEP_MESSAGES=20        # 摘要后保留最近 N 条消息
```

---

## 6. 启动前端

### Docker 方式

如果使用了 `docker compose up -d`，前端已自动启动在 http://localhost:3001。

### 本地开发方式

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端将在 http://localhost:3000 启动，自动代理 `/api` 请求到后端 `http://localhost:8000`。

---

## 7. 验证服务

### 7.1 检查后端健康状态

```bash
curl http://localhost:8000/api/v1/health
```

预期返回：

```json
{"status": "healthy"}
```

### 7.2 查看 API 文档

浏览器打开 http://localhost:8000/docs，可以看到所有可用的 API 端点。

---

## 8. 第一次对话

### 8.1 通过前端 UI

1. 打开前端页面（http://localhost:3000 或 http://localhost:3001）
2. 点击 **注册**，创建一个新账号
3. 登录后自动进入聊天页面
4. 在顶部选择 **Agent 模式**（默认 Single）
5. 输入消息开始对话

### 8.2 通过 API（命令行）

**步骤 1：注册用户**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test123456"}'
```

**步骤 2：登录获取 Token**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test123456"}'
```

返回结果中包含 `access_token`，后续请求需携带。

**步骤 3：创建会话**

```bash
curl -X POST http://localhost:8000/api/v1/auth/session \
  -H "Authorization: Bearer <your-access-token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My First Chat"}'
```

返回的 `id` 即为 `session_id`。

**步骤 4：发送消息**

```bash
curl -X POST http://localhost:8000/api/v1/chatbot/chat \
  -H "Authorization: Bearer <your-access-token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "你好，介绍一下你自己", "session_id": "<your-session-id>"}'
```

---

## 9. 核心功能速览

### 9.1 Skills 技能系统

Agent 支持按需加载专业技能，减少 system prompt 的 token 消耗。

- **预置技能** 位于 `app/core/skills/prompts/*.md`
- 对话中可说 "创建一个 XX 技能" 让 Agent 自动生成
- 自动生成的技能保存在 `app/core/skills/prompts/_auto/`

### 9.2 MCP 外部工具集成

通过 `mcp_servers.json` 配置外部 MCP 服务器：

```json
{
  "servers": [
    {
      "name": "my-tool",
      "transport": "sse",
      "url": "http://localhost:8001/sse",
      "enabled": true
    }
  ]
}
```

重启后端后 Agent 自动发现并注册新工具。

### 9.3 RAG 知识库检索

通过 `rag_providers.json` 配置知识库数据源，支持：

| Provider     | 说明                                     |
| ------------ | ---------------------------------------- |
| **Qdrant**   | 本地向量数据库                           |
| **pgvector** | PostgreSQL 向量扩展                      |
| **RAGFlow**  | 外部 RAGFlow 服务                        |
| **HTTP**     | 任意 REST API（Dify / FastGPT / 自定义） |

Agent 在对话中可通过 `retrieve_knowledge` 工具自动检索相关知识。

### 9.4 HITL 人工审批

当 Agent 调用包含敏感操作（如 `delete`、`execute_sql`、`send_email`）的工具时，系统会自动拦截并等待人工审批。

- 前端审批页面：http://localhost:3000/approvals
- API 端点：`GET /api/v1/approvals/pending`

### 9.5 知识库管理（RAG 文档导入）

前端侧边栏点击 **「知识库」** 进入文档管理页面（`/knowledge`），支持：
- 拖拽或点击上传 **PDF / TXT / Markdown / DOCX** 文件（最大 50MB）
- 上传后自动解析 → 文本切块 → 向量化 → 写入 Qdrant
- 聊天中 Agent 通过 `retrieve_knowledge` 工具自动检索知识库内容

API 端点：`POST /api/v1/rag/upload`、`GET /api/v1/rag/documents`、`DELETE /api/v1/rag/documents/{doc_id}`

### 9.6 长期记忆

Agent 自动提取对话中的重要信息，存储到 PostgreSQL（pgvector），在后续对话中根据语义相似度检索相关记忆。

---

## 10. 四种 Agent 模式

前端顶部可切换 Agent 模式，不同模式适用于不同场景：

| 模式         | API 路径                    | 适用场景                             |
| ------------ | --------------------------- | ------------------------------------ |
| **Single**   | `/chatbot/chat?mode=single` | 单 Agent + Middleware 增强           |
| **Multi**    | `/chatbot/chat?mode=multi`  | 多 Agent 协作（Supervisor + Worker） |
| **Workflow** | `/chatbot/workflow/chat`    | 多步编排任务（可选模板）             |

### Workflow 模板

Workflow 模式支持预定义的 YAML 模板，位于 `app/core/langgraph/workflow/templates/*.yaml`。在前端选择 Workflow 模式后，可选择具体的模板执行多步任务。

---

## 11. 常用 Makefile 命令

### 本地开发

```bash
make dev                  # 开发模式启动（热重载）
make staging              # Staging 环境启动
make prod                 # 生产环境启动
```

### Docker 操作

```bash
docker compose up -d                                                     # 启动完整服务栈
docker compose down                                                      # 停止完整服务栈
docker compose logs -f                                                   # 查看所有服务日志
docker compose -f docker-compose-base.yml up -d                          # 仅启动基础设施 (db + qdrant)
docker compose -f docker-compose-base.yml -f docker-compose-monitoring.yml up -d  # 基础设施 + 监控
```

### 代码质量

```bash
make lint                 # 代码检查（ruff）
make format               # 代码格式化（ruff）
```

### 模型评估

```bash
make eval                 # 交互式评估
make eval-quick           # 快速评估（默认参数）
```

---

## 12. 常见问题

### Q: Windows 上 `make dev` 报错 `uvloop` 不可用？

Windows 不支持 `uvloop`。请使用项目根目录下的 `run.py`：

```bash
python run.py
```

它会自动切换到 `WindowsSelectorEventLoopPolicy` 以兼容 `psycopg`（LangGraph 所需）。

### Q: 数据库连接失败？

1. 确认 PostgreSQL 服务正在运行
2. 确认 `.env` 中 `POSTGRES_HOST` 的值：
   - Docker 内部：`db`
   - 本地：`localhost`
3. 确认 `pgvector` 扩展已安装（Docker 镜像 `pgvector/pgvector:pg16` 已内置）

### Q: 如何使用国内 LLM API？

设置 `OPENAI_API_BASE` 为兼容 OpenAI 协议的 API 地址：

```bash
# 示例：DeepSeek
OPENAI_API_BASE=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-your-deepseek-key
DEFAULT_LLM_MODEL=deepseek-chat
```

### Q: 如何禁用 Langfuse 追踪？

将 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY` 留空即可：

```bash
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

### Q: 前端无法连接后端？

- **本地开发**：确保后端运行在 `8000` 端口，前端 Vite 会自动代理 `/api` 请求
- **Docker 部署**：前端通过 Nginx 反向代理连接后端，确认 `docker-compose.yml` 中 `app` 服务正常运行

### Q: 如何添加自定义工具？

1. 在 `app/core/langgraph/tools/` 创建新工具文件
2. 使用 `@tool` 装饰器定义工具函数
3. 在 `app/core/langgraph/tools/__init__.py` 中注册导出

### Q: 表没有自动创建？

ORM 通常会自动创建表。如遇问题，手动执行：

```bash
psql -h localhost -U <user> -d <db> -f schema.sql
```

---

## 13. 下一步

- **详细架构文档** → [`docs/PROJECT_DOCUMENTATION_CN.md`](./PROJECT_DOCUMENTATION_CN.md)
- **新功能详细指南** → [`docs/NEW_FEATURES_GUIDE.md`](./NEW_FEATURES_GUIDE.md)
- **AI Agent 开发指南** → [`AGENTS.md`](../AGENTS.md)（适合 AI 辅助开发）
- **安全策略** → [`SECURITY.md`](../SECURITY.md)

---

> **遇到问题？** 请查看 [常见问题](#12-常见问题) 或在项目仓库提交 Issue。
