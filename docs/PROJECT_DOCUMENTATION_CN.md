# FastAPI LangGraph Agent 项目文档

## 1. 项目概述

本项目是一个**生产级 AI Agent 应用模板**，基于 FastAPI 和 LangGraph 构建，提供了一个完整的 AI 聊天机器人解决方案。

### 1.1 核心技术栈

| 技术 | 用途 |
|------|------|
| **FastAPI** | 高性能异步 REST API 框架 |
| **LangGraph** | AI Agent 状态化工作流编排 |
| **LangChain** | LLM 抽象层和工具调用 |
| **Langfuse** | LLM 可观测性和追踪 |
| **PostgreSQL + pgvector** | 数据持久化和向量存储 |
| **Qdrant** | 向量数据库（RAG 知识库检索） |
| **mem0ai** | 长期记忆管理 |
| **SQLModel** | ORM 数据库模型 |
| **Prometheus + Grafana** | 监控和可视化 |
| **httpx** | 异步 HTTP 客户端（RAG 外部 API） |
| **asyncpg** | 异步 PostgreSQL 驱动 |

### 1.2 主要功能

- **AI 聊天**：支持普通聊天和流式响应
- **长期记忆**：基于语义的用户记忆存储和检索
- **工具调用**：Agent 可以调用外部工具（如 DuckDuckGo 搜索）
- **Skills 系统**：渐进式技能加载，按需加载专业指令减少上下文占用
- **SkillCreator**：LLM 自动创建 Skill + 增量学习，支持从对话提取知识、指令生成、版本管理和持久化
- **MCP 集成**：支持 Model Context Protocol，动态连接外部 MCP 服务器
- **Multi-Agent**：Supervisor + Worker 多智能体架构，自动路由到专业 Agent
- **Human-in-the-Loop**：敏感操作人工审批机制，支持审批/拒绝工作流
- **Workflow 编排**：基于 Orchestrator-Worker + Send API 的多步并行工作流引擎，支持 YAML 模板和 LLM 动态规划
- **RAG 知识库**：可插拔 Provider 架构，支持 Qdrant、pgvector、RAGFlow、通用 HTTP（Dify/FastGPT/自定义）多源检索
- **前端界面**：React + TailwindCSS 现代 UI，支持聊天、登录、审批管理、国际化、连接恢复
- **会话管理**：用户和会话的 CRUD 操作
- **JWT 认证**：基于 Token 的安全认证
- **速率限制**：可配置的 API 限流
- **可观测性**：完整的日志、指标和追踪

---

## 2. 项目结构

```
fastapi-langgraph-agent-production-ready-template/
├── app/                          # 应用主目录
│   ├── main.py                   # FastAPI 应用入口
│   ├── api/
│   │   └── v1/
│   │       ├── api.py            # API 路由聚合
│   │       ├── auth.py           # 认证端点
│   │       ├── chatbot_v1.py     # 聊天端点（V1 create_agent 实现）
│   │       ├── chatbot_workflow.py # Workflow 编排端点
│   │       ├── approval.py       # HITL 审批端点
│   │       └── sse.py            # SSE 流式响应工具
│   ├── core/
│   │   ├── config.py             # 配置管理
│   │   ├── logging.py            # 日志设置
│   │   ├── metrics.py            # Prometheus 指标
│   │   ├── middleware.py         # 自定义中间件
│   │   ├── limiter.py            # 速率限制
│   │   ├── langgraph/
│   │   │   ├── base.py           # Agent 基础工具（checkpointer、模型初始化等）
│   │   │   ├── agents/           # Multi-Agent Worker 模块
│   │   │   │   └── workers.py    # Worker Agent (researcher/coder/analyst)
│   │   │   ├── hitl/             # Human-in-the-Loop 模块
│   │   │   │   └── manager.py    # 审批管理器
│   │   │   ├── tools/            # Agent 工具
│   │   │   │   ├── __init__.py   # 工具注册
│   │   │   │   ├── duckduckgo_search.py  # DuckDuckGo 搜索工具
│   │   │   │   └── rag_retrieve.py  # RAG 知识库检索工具
│   │   │   ├── v1/               # V1 实现 (LangChain create_agent)
│   │   │   │   ├── __init__.py   # 导出 V1Agent, V1MultiAgent
│   │   │   │   ├── agent.py      # 单 Agent (create_agent + Middleware)
│   │   │   │   ├── middleware.py  # 自定义 Middleware (HITL/记忆/追踪/指标)
│   │   │   │   └── multi_agent.py # 多 Agent (Supervisor + handoff tools)
│   │   │   └── workflow/         # Workflow 编排引擎
│   │   │       ├── __init__.py   # 模块导出
│   │   │       ├── schema.py     # Workflow 数据模型
│   │   │       ├── planner.py    # WorkflowPlanner (模板+LLM 规划)
│   │   │       ├── templates.py  # YAML 模板加载器
│   │   │       ├── graph.py      # WorkflowGraph (Orchestrator-Worker+Send)
│   │   │       └── templates/    # 预置 YAML 工作流模板
│   │   │           ├── code_review.yaml
│   │   │           └── research_report.yaml
│   │   ├── skills/               # Skills 渐进式加载系统
│   │   │   ├── __init__.py       # 模块导出
│   │   │   ├── schema.py         # Skill 数据模型
│   │   │   ├── registry.py       # SkillRegistry + load/create/update_skill 工具
│   │   │   ├── creator.py        # SkillCreator（LLM 自动创建/增量学习）
│   │   │   └── prompts/          # 预置技能 Markdown 文件
│   │   │       ├── api_design.md
│   │   │       ├── code_review.md
│   │   │       ├── data_analysis.md
│   │   │       ├── sql_query.md
│   │   │       └── _auto/        # 自动生成 Skill 持久化目录
│   │   ├── rag/                  # RAG 知识库集成模块
│   │   │   ├── __init__.py       # 模块导出
│   │   │   ├── schema.py         # RAGDocument, RetrievalQuery, RetrievalResult
│   │   │   ├── base.py           # BaseRetriever 抽象基类（Provider 接口）
│   │   │   ├── manager.py        # RetrieverManager（注册、并行检索、结果合并去重）
│   │   │   └── providers/        # Provider 实现
│   │   │       ├── __init__.py   # PROVIDER_REGISTRY
│   │   │       ├── qdrant.py     # QdrantRetriever（Qdrant 向量数据库）
│   │   │       ├── pgvector.py   # PgvectorRetriever（PostgreSQL pgvector）
│   │   │       ├── ragflow.py    # RAGFlowRetriever（RAGFlow + OpenAI 兼容 API）
│   │   │       └── http.py       # GenericHTTPRetriever（Dify / FastGPT / 自定义 REST）
│   │   ├── mcp/                  # MCP 集成模块
│   │   │   ├── __init__.py
│   │   │   └── client.py         # MCP 客户端管理器
│   │   └── prompts/
│   │       ├── __init__.py
│   │       └── system.md         # 系统提示词
│   ├── models/
│   │   ├── base.py               # 模型基类
│   │   ├── user.py               # 用户模型
│   │   ├── session.py            # 会话模型
│   │   ├── thread.py             # 线程模型
│   │   └── database.py           # 数据库模型导出
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py               # 认证 Schema
│   │   ├── chat.py               # 聊天 Schema
│   │   └── approval.py           # 审批 Schema
│   ├── services/
│   │   ├── __init__.py
│   │   ├── database.py           # 数据库服务
│   │   └── llm.py                # LLM 服务（带重试）
│   └── utils/
│       ├── __init__.py
│       ├── auth.py               # 认证工具函数
│       ├── graph.py              # Graph 工具函数
│       └── sanitization.py       # 输入清洗
├── frontend/                     # React 前端应用
│   ├── Dockerfile                # 多阶段构建（node build + nginx 部署）
│   ├── index.html                # HTML 入口
│   ├── vite.config.js            # Vite + API proxy + manualChunks 代码分割
│   ├── tailwind.config.js        # TailwindCSS 配置
│   ├── postcss.config.js         # PostCSS 配置
│   ├── package.json              # 前端依赖
│   └── src/
│       ├── main.jsx              # React 入口
│       ├── App.jsx               # 路由 + 全局认证 + 401 自动登出
│       ├── api.js                # 后端 API 封装层（全局 401 拦截）
│       ├── index.css             # 全局样式
│       ├── components/
│       │   └── MarkdownRenderer.jsx  # Markdown 渲染（GFM + 代码高亮 + Copy）
│       ├── i18n/                 # 国际化
│       │   ├── LanguageContext.jsx
│       │   ├── zh.json
│       │   └── en.json
│       └── pages/
│           ├── LoginPage.jsx     # 登录/注册
│           ├── ChatPage.jsx      # 聊天（SSE + 会话侧栏 + Markdown）
│           └── ApprovalsPage.jsx # HITL 审批管理
├── tests/                        # 测试套件
├── evals/                        # 模型评估框架
├── grafana/                      # Grafana 仪表板
├── prometheus/                   # Prometheus 配置
├── scripts/                      # Docker & 部署脚本
├── docker-compose.yml            # Docker Compose 主文件（include base+monitoring）
├── docker-compose-base.yml       # 基础设施（PostgreSQL + Qdrant）
├── docker-compose-monitoring.yml  # 监控服务（Prometheus + Grafana + cAdvisor）
├── Dockerfile                    # 后端 Docker 镜像（三阶段构建）
├── Makefile                      # 开发命令
├── pyproject.toml                # Python 依赖
├── uv.lock                       # 依赖锁定文件
├── rag_providers.json            # RAG 知识库 Provider 配置
├── mcp_servers.json              # MCP 服务器配置
├── schema.sql                    # PostgreSQL 数据库 Schema
├── run.py                        # 跨平台启动脚本（Windows 兼容）
├── .env.example                  # 环境变量模板
├── AGENTS.md                     # AI Agent 开发指南
├── LICENSE                       # 开源协议
├── SECURITY.md                   # 安全策略
└── docs/
    ├── QUICK_START.md            # 快速入门指南
    ├── PROJECT_DOCUMENTATION_CN.md  # 本文档
    ├── NEW_FEATURES_GUIDE.md     # 新功能详细技术文档
    ├── AGENT_MODE_2_V1_SINGLE.md # V1 单 Agent 模式文档
    ├── AGENT_MODE_3_V1_MULTI.md  # V1 多 Agent 模式文档
    └── AGENT_MODE_4_WORKFLOW.md  # Workflow 模式文档
```

---

## 3. 核心调用链

### 3.1 聊天请求完整调用链

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户请求                                        │
│                     POST /api/v1/chatbot/chat                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           中间件层                                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │ LoggingContext   │→ │ MetricsMiddleware │→ │ RateLimiter      │          │
│  │ Middleware       │  │                   │  │ (slowapi)        │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           认证层                                             │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  get_current_session()                                            │       │
│  │  - 验证 JWT Token                                                  │       │
│  │  - 获取 Session 对象                                               │       │
│  │  - 绑定日志上下文 (user_id, session_id)                            │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       chatbot_v1.py - chat()                                  │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  await agent.get_response(messages, session_id, user_id)          │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      V1Agent.get_response()                           │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  1. 确保 Graph 已创建 (await create_graph())                       │       │
│  │  2. 获取相关长期记忆 (await _get_relevant_memory())                │       │
│  │  3. 配置 Langfuse 回调                                             │       │
│  │  4. 调用 Graph (await _graph.ainvoke())                           │       │
│  │  5. 后台更新长期记忆 (asyncio.create_task)                         │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LangGraph 工作流执行                                   │
│                                                                              │
│   ┌─────────────┐        ┌─────────────┐        ┌─────────────┐            │
│   │   Entry     │   →    │    chat     │   →    │  tool_call  │            │
│   │   Point     │        │    Node     │        │    Node     │            │
│   └─────────────┘        └─────────────┘        └─────────────┘            │
│                                │                       │                    │
│                                │                       │                    │
│                                ▼                       ▼                    │
│                          ┌─────────┐            ┌─────────────┐            │
│                          │   END   │     ←      │  返回 chat  │            │
│                          └─────────┘            └─────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          chat Node (_chat)                                   │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  1. 加载系统提示词 (含长期记忆)                                     │       │
│  │  2. 准备消息列表                                                   │       │
│  │  3. 调用 LLM 服务 (await llm_service.call())                      │       │
│  │  4. 处理响应 (process_llm_response)                               │       │
│  │  5. 判断是否有工具调用 → 决定下一步                                 │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LLMService.call()                                   │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  - 自动重试机制 (tenacity: 最多3次, 指数退避)                       │       │
│  │  - 循环模型降级 (gpt-5-mini → gpt-5 → gpt-5-nano → gpt-4o → ...)  │       │
│  │  - 错误处理 (RateLimitError, APITimeoutError, APIError)           │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          返回响应                                            │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  ChatResponse(messages=[...])                                     │       │
│  └──────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 LangGraph 状态图

```
                    ┌───────────────────┐
                    │    GraphState     │
                    │  ┌─────────────┐  │
                    │  │  messages   │  │  (消息列表, 使用 add_messages 注解)
                    │  │long_term_   │  │
                    │  │  memory     │  │  (长期记忆字符串)
                    │  └─────────────┘  │
                    └───────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │   START ──→ chat ──→ [有工具调用?]                       │
    │                           │                             │
    │                     ┌─────┴─────┐                       │
    │                     │           │                       │
    │                    Yes         No                       │
    │                     │           │                       │
    │                     ▼           ▼                       │
    │               tool_call       END                       │
    │                     │                                   │
    │                     └─────────→ chat (循环)              │
    │                                                         │
    └─────────────────────────────────────────────────────────┘
```

### 3.3 认证流程

```
┌────────────────────────────────────────────────────────────────────────────┐
│                            用户注册流程                                      │
│                                                                            │
│  POST /api/v1/auth/register                                                │
│       │                                                                    │
│       ▼                                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐│
│  │ 输入验证    │ →  │ 密码强度    │ →  │ 创建用户    │ →  │ 生成 JWT    ││
│  │ (Pydantic)  │    │ 检查        │    │ (hash 密码) │    │ Token       ││
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘│
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                            用户登录流程                                      │
│                                                                            │
│  POST /api/v1/auth/login                                                   │
│       │                                                                    │
│       ▼                                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│  │ 验证邮箱    │ →  │ 验证密码    │ →  │ 生成 JWT    │                    │
│  │             │    │ (bcrypt)    │    │ Token       │                    │
│  └─────────────┘    └─────────────┘    └─────────────┘                    │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│                            会话创建流程                                      │
│                                                                            │
│  POST /api/v1/auth/session (需要 User Token)                               │
│       │                                                                    │
│       ▼                                                                    │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                    │
│  │ 验证用户    │ →  │ 创建 Session│ →  │ 生成 Session│                    │
│  │ Token       │    │ (UUID)      │    │ Token       │                    │
│  └─────────────┘    └─────────────┘    └─────────────┘                    │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. API 端点详解

### 4.1 认证端点 (`/api/v1/auth`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/register` | POST | 用户注册 | 无 |
| `/login` | POST | 用户登录 | 无 |
| `/session` | POST | 创建聊天会话 | User Token |
| `/session/{session_id}/name` | PATCH | 更新会话名称 | Session Token |
| `/session/{session_id}` | DELETE | 删除会话 | Session Token |
| `/sessions` | GET | 获取用户所有会话 | User Token |

### 4.2 聊天端点 (`/api/v1/chatbot`)

> 基于 LangChain v1 `create_agent` + Middleware 的现代实现。支持通过 `mode` 参数切换单 Agent / 多 Agent。

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/chat?mode=single` | POST | V1 单 Agent 聊天（默认） | Session Token |
| `/chat?mode=multi` | POST | V1 多 Agent 聊天（Supervisor 路由） | Session Token |
| `/chat/stream?mode=single` | POST | V1 单 Agent 流式响应 | Session Token |
| `/chat/stream?mode=multi` | POST | V1 多 Agent 流式响应 | Session Token |
| `/messages` | GET | 获取 V1 会话历史 | Session Token |
| `/messages` | DELETE | 清除 V1 会话历史 | Session Token |

### 4.3 审批端点 (`/api/v1/approvals`)

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/pending` | GET | 获取待审批请求列表 | Session Token |
| `/{id}` | GET | 获取单个审批请求详情 | Session Token |
| `/{id}/approve` | POST | 批准审批请求 | Session Token |
| `/{id}/reject` | POST | 拒绝审批请求 | Session Token |

### 4.4 Workflow 编排端点 (`/api/v1/chatbot/workflow`)

> 基于 LangGraph Orchestrator-Worker + Send API 的多步工作流编排引擎，支持并行执行和依赖链调度。

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/chat` | POST | 执行 Workflow（可选 `?template=code_review`） | Session Token |
| `/chat/stream` | POST | 流式执行 Workflow | Session Token |
| `/templates` | GET | 列出可用 Workflow 模板 | Session Token |

### 4.5 健康检查端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/` | GET | API 基本信息 |
| `/health` | GET | 健康检查（含数据库状态）|
| `/metrics` | GET | Prometheus 指标 |

---

## 5. 如何启动

### 5.1 前置条件

- Python 3.13+
- PostgreSQL (支持 pgvector 扩展)
- Docker 和 Docker Compose (可选)

### 5.2 本地开发启动

```bash
# 1. 克隆仓库
git clone <repository-url>
cd fastapi-langgraph-agent-production-ready-template

# 2. 安装依赖
pip install uv
uv sync

# 3. 创建环境配置文件
cp .env.example .env

# 4. 编辑 .env 配置必要参数
# - OPENAI_API_KEY: OpenAI API 密钥
# - POSTGRES_*: 数据库连接信息
# - JWT_SECRET_KEY: JWT 密钥
# - LANGFUSE_*: Langfuse 配置 (可选)

# 5. 启动应用
make dev
```

> **Windows 用户**：`make dev` 使用 `uvloop`，Windows 不支持。请使用项目根目录的 `run.py`：
> ```bash
> python run.py
> ```
> 它会自动切换到 `WindowsSelectorEventLoopPolicy` 以兼容 `psycopg`。

### 5.3 使用 Docker 启动

```bash
# 1. 创建环境配置文件
cp .env.example .env

# 2a. 启动完整服务栈（后端 + 数据库 + Qdrant + 前端 + 监控）
docker compose up -d

# 2b. 或只启动基础设施（数据库 + Qdrant）
docker compose -f docker-compose-base.yml up -d

# 3. 访问服务
# - 后端 API:  http://localhost:8000
# - Swagger:    http://localhost:8000/docs
# - 前端 UI:    http://localhost:3001  (Docker Compose 启动时)
# - Prometheus: http://localhost:9090
# - Grafana:    http://localhost:3000 (admin/admin)
# - Qdrant:     http://localhost:6333
```

Docker Compose 包含的服务：

| 服务 | 镜像 | 端口 |
|------|------|------|
| **app** | 本地构建 | 8000 |
| **db** | pgvector/pgvector:pg16 | 5432 |
| **qdrant** | qdrant/qdrant:latest | 6333, 6334 |
| **frontend** | 本地构建 (Nginx) | 3001 |
| **prometheus** | prom/prometheus:latest | 9090 |
| **grafana** | grafana/grafana:latest | 3000 |
| **cadvisor** | gcr.io/cadvisor/cadvisor | 8080 |

### 5.4 环境配置说明

项目支持三种环境：

| 环境 | 配置文件 | 特点 |
|------|----------|------|
| development | `.env` (DEBUG=true) | 控制台日志, 宽松限流 |
| staging | `.env` (DEBUG=false) | JSON日志, 中等限流 |
| production | `.env` (DEBUG=false) | JSON日志, 严格限流 |

### 5.5 关键环境变量

```bash
# 应用设置
APP_ENV=development          # 环境: development/staging/production
PROJECT_NAME="Web Assistant" # 项目名称
DEBUG=true                   # 调试模式

# LLM 设置 (必须)
OPENAI_API_KEY=sk-xxx        # OpenAI API 密钥
OPENAI_API_BASE=              # 自定义 API 地址（可选，如 DeepSeek、Azure OpenAI）
DEFAULT_LLM_MODEL=gpt-4o-mini # 默认模型

# 数据库设置 (必须)
POSTGRES_HOST=localhost       # Docker 内部用 db
POSTGRES_PORT=5432
POSTGRES_DB=mydb
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mypassword

# JWT 设置 (必须)
JWT_SECRET_KEY=your-secret-key

# Langfuse 设置 (可选，用于追踪，留空即禁用)
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
LANGFUSE_HOST=https://cloud.langfuse.com

# Qdrant 设置 (可选，RAG 知识库检索)
QDRANT_HOST=qdrant            # Docker 内部用 qdrant，本地用 localhost
QDRANT_PORT=6333
QDRANT_API_KEY=               # 如有认证填写

# 长期记忆设置 (可选)
LONG_TERM_MEMORY_MODEL=gpt-4o-mini
LONG_TERM_MEMORY_EMBEDDER_MODEL=text-embedding-3-small
LONG_TERM_MEMORY_COLLECTION_NAME=longterm_memory
```

> **注意**：长期记忆（mem0ai）使用主 PostgreSQL 数据库的同一连接（`POSTGRES_*`），不需要单独的数据库实例。

---

## 6. 如何使用

### 6.1 使用 Swagger UI

1. 启动应用后访问 `http://localhost:8000/docs`
2. 按照以下流程测试 API

### 6.2 使用 curl 命令示例

#### 6.2.1 用户注册

```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

**响应:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "token": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_at": "2024-02-29T12:00:00Z"
  }
}
```

#### 6.2.2 用户登录

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=SecurePass123!&grant_type=password"
```

#### 6.2.3 创建聊天会话

```bash
curl -X POST "http://localhost:8000/api/v1/auth/session" \
  -H "Authorization: Bearer <USER_TOKEN>"
```

**响应:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "",
  "token": {
    "access_token": "eyJ...",
    "token_type": "bearer",
    "expires_at": "2024-02-29T12:00:00Z"
  }
}
```

#### 6.2.4 发送聊天消息

```bash
curl -X POST "http://localhost:8000/api/v1/chatbot/chat" \
  -H "Authorization: Bearer <SESSION_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "你好，请介绍一下你自己"}
    ]
  }'
```

#### 6.2.5 流式聊天

```bash
curl -X POST "http://localhost:8000/api/v1/chatbot/chat/stream" \
  -H "Authorization: Bearer <SESSION_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "写一首关于编程的诗"}
    ]
  }'
```

#### 6.2.6 获取聊天历史

```bash
curl -X GET "http://localhost:8000/api/v1/chatbot/messages" \
  -H "Authorization: Bearer <SESSION_TOKEN>"
```

#### 6.2.7 清除聊天历史

```bash
curl -X DELETE "http://localhost:8000/api/v1/chatbot/messages" \
  -H "Authorization: Bearer <SESSION_TOKEN>"
```

### 6.3 使用 Workflow 编排 API

Workflow API 支持多步骤、多 Worker 并行协作的工作流编排。

#### 6.3.1 使用预定义模板执行 Workflow

```bash
curl -X POST "http://localhost:8000/api/v1/chatbot/workflow/chat?template=code_review" \
  -H "Authorization: Bearer <SESSION_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "审查这段代码: def foo(): pass"}]}'
```

#### 6.3.2 LLM 动态规划 Workflow

```bash
curl -X POST "http://localhost:8000/api/v1/chatbot/workflow/chat" \
  -H "Authorization: Bearer <SESSION_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "调研 Python 异步框架并写对比报告"}]}'
```

#### 6.3.3 查看可用 Workflow 模板

```bash
curl -X GET "http://localhost:8000/api/v1/chatbot/workflow/templates" \
  -H "Authorization: Bearer <SESSION_TOKEN>"
```

### 6.4 聊天 API

基于 LangChain `create_agent` + Middleware 模式的 Agent 实现。支持单 Agent 和多 Agent 模式。

#### 6.4.1 V1 单 Agent 聊天

```bash
curl -X POST "http://localhost:8000/api/v1/chatbot/chat" \
  -H "Authorization: Bearer <SESSION_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "你好，请介绍一下你自己"}
    ]
  }'
```

#### 6.4.2 V1 多 Agent 聊天（Supervisor 路由）

添加 `mode=multi` 参数即可切换到多 Agent 模式，Supervisor 会自动将请求路由给最合适的 Worker（researcher / coder / analyst）：

```bash
curl -X POST "http://localhost:8000/api/v1/chatbot/chat?mode=multi" \
  -H "Authorization: Bearer <SESSION_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "帮我分析这组销售数据的趋势"}
    ]
  }'
```

#### 6.4.3 V1 流式聊天

```bash
curl -X POST "http://localhost:8000/api/v1/chatbot/chat/stream?mode=single" \
  -H "Authorization: Bearer <SESSION_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "写一首关于编程的诗"}
    ]
  }'
```

### 6.5 Python 客户端示例

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# 1. 注册用户
response = requests.post(f"{BASE_URL}/auth/register", json={
    "email": "user@example.com",
    "password": "SecurePass123!"
})
user_data = response.json()
user_token = user_data["token"]["access_token"]

# 2. 创建会话
response = requests.post(
    f"{BASE_URL}/auth/session",
    headers={"Authorization": f"Bearer {user_token}"}
)
session_data = response.json()
session_token = session_data["token"]["access_token"]

# 3. 发送消息（单 Agent）
response = requests.post(
    f"{BASE_URL}/chatbot/chat",
    headers={"Authorization": f"Bearer {session_token}"},
    json={"messages": [{"role": "user", "content": "Hello!"}]}
)
print("V1 Single:", response.json()["messages"])

# 4. 发送消息（多 Agent）
response = requests.post(
    f"{BASE_URL}/chatbot/chat?mode=multi",
    headers={"Authorization": f"Bearer {session_token}"},
    json={"messages": [{"role": "user", "content": "分析这段代码的性能问题"}]}
)
print("V1 Multi:", response.json()["messages"])
```

---

## 7. 核心组件详解

### 7.1 LLMService (app/services/llm.py)

**功能**: 管理 LLM 调用，提供自动重试和模型降级机制。

**关键特性**:
- 支持多模型注册 (gpt-5-mini, gpt-5, gpt-5-nano, gpt-4o, gpt-4o-mini)
- 使用 tenacity 实现指数退避重试 (最多3次)
- 循环模型降级：当前模型失败后自动切换到下一个
- 工具绑定支持

### 7.2 BaseAgentMixin (app/core/langgraph/base.py)

**功能**: 提供所有 Agent 共享的基础设施方法。

**关键特性**:
- 基于 StateGraph 的状态机，手动定义 `chat` → `tool_call` 节点
- PostgreSQL 检查点持久化
- 长期记忆集成 (mem0ai)
- 工具调用节点支持
- 流式响应支持

### 7.3 V1Agent (app/core/langgraph/v1/agent.py)

**功能**: 基于 LangChain v1 `create_agent` 的现代 Agent 实现。

**关键特性**:
- 使用 `create_agent(model, tools, middleware)` 一行创建 Agent（传入 `LLMRegistry.get()` 预初始化的模型实例）
- **Middleware 栈**遵循官方 [Context Engineering](https://docs.langchain.com/oss/python/langchain/context-engineering) 指南：
  - `@dynamic_prompt skills_aware_prompt` — 动态构建含 Skills + 长期记忆的系统提示词
  - `SummarizationMiddleware` — 自动压缩长对话历史，防止 context 溢出（内置）
  - `@wrap_model_call role_based_tool_filter` — 按用户角色动态过滤工具集
  - `LangfuseTracingMiddleware` — 记录模型调用事件（logging-only）；实际追踪由 config 层 `LangfuseCallbackHandler` 完成
  - `MetricsMiddleware` — Prometheus 推理耗时打点（含 `awrap_model_call` 异步支持）
  - `HITLApprovalMiddleware` — 拦截敏感工具调用，要求人工审批
- Langfuse 追踪通过 `get_stream_response()` 中 `config["callbacks"]` 注入 `LangfuseCallbackHandler()`
- MCP 工具自动集成
- PostgreSQL 检查点持久化（使用 `aget_state()` 异步 API）
- 流式响应支持

**架构对比**:

```
Agent 创建方式（v1/agent.py）:
  create_agent(model, tools, middleware=[...]) → 一切自动处理
```

### 7.4 V1MultiAgent (app/core/langgraph/v1/multi_agent.py)

**功能**: 基于 LangChain v1 的多 Agent 系统，使用 Supervisor + handoff tools 模式。

**架构**:

```
用户请求 → Supervisor Agent (create_agent + handoff_tools)
                  ├─ transfer_to_researcher → Researcher Agent (create_agent)
                  ├─ transfer_to_coder      → Coder Agent (create_agent)
                  ├─ transfer_to_analyst    → Analyst Agent (create_agent)
                  └─ 直接回答（通用问题）
```

**关键特性**:
- Supervisor 通过 handoff tools 自动路由（不再需要 JSON 解析），扫描所有响应消息检测 handoff 工具调用
- 每个 Worker 是独立的 `create_agent` 实例（传入 `LLMRegistry.get()` 模型实例），拥有自己的 Middleware
- `supervisor_node` 和 `worker_node` 显式接收并转发 `config` 参数，确保 Langfuse `CallbackHandler` 传播到子图
- 支持通过 `register_worker()` 动态注册新 Worker
- 请求/响应格式与单 Agent 完全兼容

**添加新 Worker**:

```python
from app.core.langgraph.v1.multi_agent import register_worker

register_worker(
    name="translator",
    system_prompt="You are an expert translator specializing in...",
    description="Multi-language translation with cultural context",
)
```

### 7.5 WorkflowGraph — Workflow 编排引擎 (app/core/langgraph/workflow/graph.py)

**功能**: 基于 LangGraph Orchestrator-Worker + Send API 的多步工作流编排引擎。

**关键特性**:
- 使用 `Send` API 将独立步骤并行 fan-out 到多个 Worker
- 依赖链调度：有依赖关系的步骤按轮次顺序执行
- 支持 YAML 预定义模板和 LLM 动态规划两种模式
- `WorkflowPlanner` 自动匹配模板或调用 LLM 生成执行计划
- `WorkflowTemplateRegistry` 扫描 `workflow/templates/*.yaml` 自动加载
- Synthesizer 节点合并所有 Worker 输出为最终响应
- PostgreSQL 检查点持久化
- 流式响应支持

### 7.6 SkillCreator — LLM 自动创建技能 (app/core/skills/creator.py)

**功能**: LLM 驱动的技能自动生成和增量学习。

**关键特性**:
- 从用户指令自动生成新 Skill（`create_from_instruction`）
- 从对话历史中提取可复用知识（`create_from_conversation`）
- 增量更新已有 Skill，智能合并新知识（`update_skill`）
- 自动持久化到 `prompts/_auto/` 目录，应用重启后自动加载
- 版本管理：每次更新自动递增 `version`
- Agent 工具：`create_skill`、`update_skill`、`list_all_skills`

### 7.7 DatabaseService (app/services/database.py)

**功能**: 数据库操作服务。

**关键特性**:
- 连接池管理 (QueuePool)
- 用户 CRUD 操作
- 会话 CRUD 操作
- 健康检查

### 7.8 长期记忆系统

**功能**: 基于语义的用户记忆管理。

**工作流程**:
1. 用户发送消息时，检索相关记忆
2. 将记忆注入系统提示词
3. 对话完成后，后台异步更新记忆

---

## 8. 监控和可观测性

### 8.1 日志

- 使用 **structlog** 结构化日志
- 自动绑定 request_id, session_id, user_id
- 开发环境: 彩色控制台输出
- 生产环境: JSON 格式

### 8.2 指标 (Prometheus)

- API 请求延迟
- LLM 调用延迟
- 速率限制统计
- 数据库连接状态

### 8.3 追踪 (Langfuse)

- LLM 调用追踪
- Token 使用统计
- 成本分析
- 会话回放

**追踪注入策略**：所有 Agent 模式统一通过 `config["callbacks"]` 注入 `LangfuseCallbackHandler()`：

| Agent 模式 | 注入位置 | config 传播方式 |
|-----------|---------|----------------|
| V1 Single | `get_stream_response()` | `agent.astream(input, config)` 自动传播 |
| V1 Multi | `get_stream_response()` | `supervisor_node(state, config)` → `supervisor.ainvoke(state, config=config)`；`worker_node(state, config)` → `agent.ainvoke(state, config=config)` 显式转发 |
| Workflow | `get_stream_response()` | `graph.astream(input, config)` 自动传播 |

V1 的 `LangfuseTracingMiddleware` 仅做日志记录（logging-only），不注入 callbacks，避免与 LangGraph 内部 callback 机制冲突。

---

## 9. 模型评估

项目包含评估框架，用于测量模型性能：

```bash
# 交互模式
make eval ENV=development

# 快速模式
make eval-quick ENV=development

# 不生成报告
make eval-no-report ENV=development
```

评估报告保存在 `evals/reports/` 目录。

---

## 10. Skills 渐进式加载系统

### 10.1 概念

Skills 系统实现了 **Progressive Disclosure（渐进式披露）** 模式：
- 系统提示词中仅包含技能的简短描述（1-2 句话）
- Agent 在需要时通过 `load_skill` 工具按需加载完整技能内容
- 减少了初始上下文占用，提高了可扩展性

### 10.2 预置技能

| 技能名称 | 描述 |
|---------|------|
| `sql_query` | SQL 查询专家，提供查询优化和安全建议 |
| `data_analysis` | 数据分析专家，结构化分析方法论 |
| `code_review` | 代码审查专家，最佳实践和安全检查 |
| `api_design` | API 设计专家，RESTful 设计规范 |

### 10.3 添加新技能（手动）

在 `app/core/skills/prompts/` 目录下创建 Markdown 文件：

```markdown
---
name: my_skill
description: 简短描述，将显示在系统提示词中
tags: tag1, tag2
---
完整的技能内容和指令...
```

技能会在应用启动时自动加载到注册表。

### 10.4 编程方式注册技能

```python
from app.core.skills import Skill, skill_registry

skill = Skill(
    name="custom_skill",
    description="自定义技能描述",
    content="详细的技能指令...",
    tags=["custom"]
)
skill_registry.register(skill)
```

### 10.5 SkillCreator — LLM 自动创建与增量学习

**SkillCreator** (`app/core/skills/creator.py`) 是基于 [skills.sh](https://skills.sh/anthropics/skills/skill-creator) 理念实现的 LLM 驱动技能自动生成器，让 Agent 在对话过程中自动发现、提取并持久化可复用知识。

#### Agent 可用工具

| 工具 | 参数 | 说明 |
|------|------|------|
| `create_skill(instruction)` | `instruction: str` | 根据指令自动创建新技能（LLM 驱动） |
| `update_skill(skill_name, new_info)` | `skill_name: str, new_info: str` | 增量更新已有技能，智能合并新知识 |
| `list_all_skills()` | 无 | 列出所有技能及版本、来源信息 |

#### 使用方式

**方式 1：对话中自然触发**

在与 Agent 对话时，使用以下表达即可触发技能创建：

- "帮我创建一个关于 Docker 部署最佳实践的技能"
- "把这个模式保存为一个技能"
- "学会这个，以后遇到类似问题就用它"
- "更新 postgresql_optimization 技能，加上连接池调优策略"

Agent 会自动调用 `create_skill` 或 `update_skill` 工具。

**方式 2：编程调用**

```python
from app.core.skills import skill_creator, skill_registry
from langchain_core.messages import HumanMessage, AIMessage

# 从指令创建
skill = await skill_creator.create_from_instruction(
    "专门处理 PostgreSQL 查询优化的技能，包括索引策略、EXPLAIN 分析",
    source="agent",
)
if skill:
    skill_registry.register_or_update(skill, persist=True)

# 从对话历史提取
messages = [
    HumanMessage(content="Docker 多阶段构建怎么优化？"),
    AIMessage(content="1. 使用 alpine 基础镜像...\n2. 分离构建和运行阶段..."),
]
skill = await skill_creator.create_from_conversation(messages, source="conversation")
if skill:
    skill_registry.register_or_update(skill, persist=True)

# 增量更新已有技能
existing = skill_registry.get("postgresql_optimization")
if existing:
    updated = await skill_creator.update_skill(existing, "新增 pg_stat_statements 监控策略")
    if updated:
        skill_registry.register_or_update(updated, persist=True)
```

#### 自动生成文件格式

自动创建的技能持久化到 `app/core/skills/prompts/_auto/` 目录：

```markdown
---
name: postgresql_optimization
description: PostgreSQL 查询优化专家，提供索引策略和 EXPLAIN 分析指南
tags: postgresql, optimization, database
version: 2
source: agent
auto_generated: true
---

# PostgreSQL Optimization
...
```

| 生命周期 | 行为 |
|---------|------|
| 首次创建 | 写入 `prompts/_auto/{name}.md`，`version=1` |
| 增量更新 | 覆盖写入同名文件，`version` 递增 |
| 应用重启 | `SkillRegistry` 自动扫描 `_auto/` 目录加载 |
| 手动删除 | `skill_registry.unregister(name)` 同时删除内存和文件 |

#### 核心类

| 类/方法 | 说明 |
|---------|------|
| `SkillCreator` | LLM 驱动的技能生成器（全局单例 `skill_creator`） |
| `create_from_instruction(instruction, source)` | 从用户指令自动生成 Skill |
| `create_from_conversation(messages, source)` | 分析对话历史提取可复用知识 |
| `update_skill(existing_skill, new_info)` | 增量合并新知识到已有 Skill |

> 详细架构、调用链和 Prompt 设计请参阅 [NEW_FEATURES_GUIDE.md §2.6](./NEW_FEATURES_GUIDE.md#26-skillcreator--llm-自动创建与增量学习)。

---

## 11. MCP（Model Context Protocol）集成

### 11.1 概念

MCP 是一个标准化协议，用于将 AI 系统与外部工具和数据源连接。本项目支持：
- **SSE 传输**：连接到运行中的 MCP HTTP 服务器
- **stdio 传输**：启动本地 MCP 进程并通过标准 I/O 通信

### 11.2 配置

编辑项目根目录的 `mcp_servers.json`：

```json
{
  "servers": [
    {
      "name": "my-sse-server",
      "transport": "sse",
      "url": "http://localhost:8001/sse",
      "enabled": true
    },
    {
      "name": "my-stdio-server",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": {},
      "enabled": true
    }
  ]
}
```

### 11.3 工作流程

1. 应用启动时，`MCPManager` 读取 `mcp_servers.json` 配置
2. Agent 初始化时异步调用 `_initialize_mcp_tools()` 连接 MCP
3. MCP 服务器的工具自动转换为 LangChain 兼容格式
4. 工具合并到 Agent 的工具列表中，LLM 可直接调用

### 11.4 依赖

MCP 集成需要以下额外依赖（已添加到 `pyproject.toml`）：
- `langchain-mcp-adapters` - LangChain MCP 适配器
- `mcp` - MCP 协议核心库

安装：`pip install langchain-mcp-adapters mcp` 或 `uv sync`

---

## 12. RAG 知识库集成

### 12.1 概述

RAG（Retrieval-Augmented Generation）模块为 Agent 提供外部知识库检索能力。采用**可插拔 Provider 架构**，通过 JSON 配置文件即可添加或切换知识源，无需修改代码。

### 12.2 架构

```
用户提问 → Agent 调用 retrieve_knowledge 工具
                    │
                    ▼
            RetrieverManager
            ┌───────┼───────┐
            ▼       ▼       ▼
         Qdrant  pgvector  RAGFlow / HTTP
            │       │       │
            └───────┼───────┘
                    ▼
            合并去重 → 返回 top-k 文档 → 注入 Agent 上下文
```

### 12.3 内置 Provider

| Provider | 类型 | 说明 |
|----------|------|------|
| `QdrantRetriever` | `qdrant` | Qdrant 向量数据库，适合本地部署 |
| `PgvectorRetriever` | `pgvector` | 复用主 PostgreSQL 的 pgvector 扩展 |
| `RAGFlowRetriever` | `ragflow` | 外部 RAGFlow 服务（数据集检索 + OpenAI 兼容聊天） |
| `GenericHTTPRetriever` | `http` | 任意 REST API（Dify、FastGPT、自定义系统） |

### 12.4 配置

编辑项目根目录的 `rag_providers.json`：

```json
{
  "providers": [
    {
      "name": "local_qdrant",
      "type": "qdrant",
      "enabled": true,
      "config": {
        "host": "qdrant",
        "port": 6333,
        "collection_name": "rag_documents",
        "embedding_model": "text-embedding-3-small",
        "score_threshold": 0.3
      }
    },
    {
      "name": "local_pgvector",
      "type": "pgvector",
      "enabled": false,
      "config": {
        "collection_name": "rag_documents",
        "embedding_model": "text-embedding-3-small"
      }
    }
  ]
}
```

- 每个 Provider 通过 `enabled` 字段控制开关
- `type` 对应 `PROVIDER_REGISTRY` 中注册的 Provider 类
- pgvector Provider 默认使用主 `POSTGRES_*` 连接配置

### 12.5 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| `BaseRetriever` | `rag/base.py` | Provider 抽象接口（`initialize`、`retrieve`、`close`） |
| `RetrieverManager` | `rag/manager.py` | 注册 Provider、并行查询、合并去重结果 |
| `RAGDocument` | `rag/schema.py` | 检索文档数据模型 |
| `PROVIDER_REGISTRY` | `rag/providers/__init__.py` | Provider 类型 → 实现类映射 |
| `retrieve_knowledge` | `tools/rag_retrieve.py` | Agent 工具：搜索所有已启用 Provider |

### 12.6 Agent 工具

Agent 在对话中通过 `retrieve_knowledge` 工具自动检索相关知识：

```python
@tool
async def retrieve_knowledge(query: str, top_k: int = 5) -> str:
    """搜索知识库获取相关文档"""
    ...
```

### 12.7 添加自定义 Provider

1. 在 `app/core/rag/providers/` 创建新文件，继承 `BaseRetriever`
2. 实现 `initialize()`、`retrieve()`、`close()` 方法
3. 在 `app/core/rag/providers/__init__.py` 的 `PROVIDER_REGISTRY` 中注册
4. 在 `rag_providers.json` 中添加配置项

### 12.8 依赖

RAG 模块使用的额外依赖（已添加到 `pyproject.toml`）：
- `qdrant-client` — Qdrant 向量数据库客户端
- `httpx` — 异步 HTTP 客户端（RAGFlow、GenericHTTP Provider）
- `langchain-postgres` — pgvector LangChain 集成
- `asyncpg` — 异步 PostgreSQL 驱动

> 详细架构和调用链请参阅 [NEW_FEATURES_GUIDE.md §15](./NEW_FEATURES_GUIDE.md#15-rag-知识库集成)。

---

## 13. Multi-Agent 多智能体架构

### 13.1 架构概述

本项目实现了 **Supervisor + Worker** 多智能体模式：

```
用户请求 → Supervisor Agent → 路由决策 → Worker Agent → 响应
                                    ├─ researcher (研究专家)
                                    ├─ coder (编程专家)
                                    ├─ analyst (数据分析专家)
                                    └─ general (通用处理)
```

### 13.2 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| V1MultiAgent | `v1/multi_agent.py` | 分析用户意图，路由到合适的 Worker |
| BaseWorker | `agents/workers.py` | Worker 基类，提供通用 invoke 接口 |
| ResearcherWorker | `agents/workers.py` | 信息搜索、事实核查、总结报告 |
| CoderWorker | `agents/workers.py` | 代码生成、调试、审查 |
| AnalystWorker | `agents/workers.py` | 数据分析、统计、可视化建议 |
| V1MultiAgent | `v1/multi_agent.py` | Supervisor + handoff tools 多 Agent 编排 |

### 13.3 工作流程

1. 用户消息进入 `supervisor` 节点
2. Supervisor 用 LLM 分析意图，输出 JSON 路由决策
3. 根据决策路由到 `worker` 或 `chat`（通用）节点
4. Worker 使用专业 system prompt 处理请求
5. 如有工具调用，进入 `tool_call` 节点执行
6. 结果返回给用户

### 13.4 扩展 Worker

在 `workers.py` 中继承 `BaseWorker` 创建新 Worker，并注册到 `WORKER_REGISTRY`：

```python
class MyWorker(BaseWorker):
    name = "my_worker"
    description = "My specialist description"
    system_prompt = "You are a specialist in ..."

WORKER_REGISTRY["my_worker"] = MyWorker()
```

---

## 14. Human-in-the-Loop 人工审批

### 14.1 概述

HITL 机制允许人类在 Agent 执行敏感操作前进行审核，避免自动化操作带来的风险。

### 14.2 审批流程

```
Agent 要执行工具 → 检查是否敏感操作 → 创建审批请求 → 等待人工审核
                                                          ├─ ✅ 批准 → 继续执行
                                                          ├─ ❌ 拒绝 → 终止操作
                                                          └─ ⏰ 超时 → 自动过期
```

### 14.3 API 端点

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/v1/approvals/pending` | 获取待审批请求列表 |
| GET | `/api/v1/approvals/{id}` | 获取单个审批请求详情 |
| POST | `/api/v1/approvals/{id}/approve` | 批准审批请求 |
| POST | `/api/v1/approvals/{id}/reject` | 拒绝审批请求 |

### 14.4 敏感操作触发规则

工具名称中包含以下关键词时自动触发审批：`delete`、`modify`、`update`、`write`、`execute_sql`、`send_email`

---

## 15. 前端界面

### 15.1 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.3 | UI 框架 |
| Vite | 6.0 | 构建工具（含 manualChunks 代码分割） |
| TailwindCSS | 3.4 | 原子化 CSS 框架 |
| React Router | 6.28 | 客户端路由 |
| Lucide React | 0.460 | SVG 图标库 |
| react-markdown | 10.1 | Markdown 渲染 |
| remark-gfm | 4.0 | GitHub Flavored Markdown 支持 |
| react-syntax-highlighter | 16.1 | 代码块语法高亮 |

### 15.2 页面组成

- **LoginPage** — 登录/注册页面，暗色渐变背景，玻璃拟态卡片
- **ChatPage** — 聊天界面，SSE 流式响应，**会话侧栏**，**Markdown 渲染**（代码高亮 + Copy），**Agent 模式切换**，消息历史加载
- **ApprovalsPage** — HITL 审批队列，实时刷新，批准/拒绝操作
- **MarkdownRenderer** — 独立 Markdown 渲染组件（`components/MarkdownRenderer.jsx`）
- **i18n/** — 国际化语言包，支持中英文切换

### 15.3 ChatPage 核心功能

#### 15.3.1 Agent 模式选择器

ChatPage 顶部栏集成了 **Agent 模式选择器**，可在以下 4 种后端 Agent 模式之间一键切换：

| 模式 | 对应后端 API | 说明 | 图标颜色 |
|------|-------------|------|---------|
| Single Agent | `/chatbot/chat/stream?mode=single` | create_agent + Middleware | 蓝色 |
| Multi Agent | `/chatbot/chat/stream?mode=multi` | Supervisor + Worker 多智能体 | 紫色 |
| Workflow | `/chatbot/workflow/chat/stream` | Orchestrator-Worker 多步工作流 | 琥珀色 |

- 选择 Workflow 模式后，额外显示**模板下拉框**，可选择预定义模板或使用 LLM 自动规划
- 模式选择通过 `localStorage` 持久化，刷新后保持
- 每种模式有独立图标和颜色标识，方便区分当前 Agent 类型
- `api.js` 中的 `buildChatUrl()` 根据模式自动构建正确的 API 路径

#### 15.3.2 会话侧栏

ChatPage 左侧集成了可折叠的暗色会话侧栏：

- 暗色主题（`bg-gray-900`），可通过按钮折叠/展开
- 侧栏状态持久化到 `localStorage`（`sidebarOpen` key）
- 显示所有会话列表，高亮当前活跃会话
- 支持切换会话（自动加载目标会话的历史消息）
- 支持删除会话（删除后自动切换到其他会话或创建新会话）
- 顶部 "New Chat" 按钮创建新会话

#### 15.3.3 Markdown 渲染

AI 回复通过 `MarkdownRenderer` 组件渲染，支持：

- **GFM 表格**：完整的 GitHub Flavored Markdown 表格渲染
- **代码块高亮**：使用 Prism（oneLight 主题）语法高亮，支持所有主流编程语言
- **代码块 Copy 按钮**：每个代码块右上角显示语言标签 + 一键复制按钮（Copy/Copied 状态）
- **行内代码**：灰色背景 + 等宽字体
- **标题/列表/引用块/链接/分割线**：完整的 Markdown 元素样式

#### 15.3.4 消息历史与 401 处理

- 页面加载时自动调用 `getMessages(sessionToken, mode)` 拉取当前会话的历史消息
- `api.js` 实现全局 401 拦截：所有 API 响应经过 `handleResponse()` 检查，401 时触发 `setAuthErrorHandler` 回调自动登出
- 切换会话时自动加载目标会话的历史消息

### 15.4 连接恢复机制

前端实现了网络连接恢复机制，提升用户体验：

- `api.js` 中 `safeFetch` 封装网络错误，`isNetworkError` 工具函数检测连接问题
- ChatPage 和 ApprovalsPage 显示 **黄色连接错误 banner**
- 每 5 秒自动重试 + 手动重试按钮
- 启动时 `validateToken` 验证 localStorage 中 token 有效性
- 401 响应防抖处理，避免多次并发请求触发重复登出
- `streamMessage` 修复双重 `onDone` 回调问题

### 15.5 Vite 代码分割

`vite.config.js` 配置了 `manualChunks` 优化构建体积：

```javascript
manualChunks: {
  'syntax-highlighter': ['react-syntax-highlighter'],
  'react-vendor': ['react', 'react-dom', 'react-router-dom'],
  'markdown': ['react-markdown', 'remark-gfm'],
}
```

### 15.6 启动前端

```bash
cd frontend
npm install
npm run dev       # 开发模式 http://localhost:3000
npm run build     # 生产构建 → dist/
npm run preview   # 预览生产构建
```

前端默认运行在 `http://localhost:3000`，通过 Vite proxy 转发 API 请求到后端 `http://localhost:8000`。

---

## 16. Workflow 编排引擎

### 16.1 概述

Workflow 编排引擎基于 **LangGraph Orchestrator-Worker + Send API** 模式，实现自由编排的多步工作流：

- **并行 fan-out**：独立步骤通过 `Send` API 并行分发到多个 Worker
- **依赖链调度**：有依赖关系的步骤按轮次顺序执行
- **YAML 模板 + LLM 动态规划**：预定义常见流程，复杂场景由 LLM 自动生成执行计划
- **结果聚合**：Synthesizer 节点合并所有 Worker 输出为最终响应

### 16.2 架构

```text
用户请求 → [planner] → [assign_workers (Send x N)] → [worker_task 并行执行]
                                                            │
                                                    [check_completion]
                                                      │           │
                                                (有更多步骤)   (全部完成)
                                                      │           │
                                              [assign_workers]  [synthesizer] → 最终响应
```

### 16.3 内置模板

| 模板名 | 流程 | 说明 |
|--------|------|------|
| `code_review` | analyst → coder → researcher | 代码审查：分析 → 审查 → 报告 |
| `research_report` | researcher → analyst → coder | 调研报告：收集 → 分析 → 撰写 |

### 16.4 添加自定义模板

在 `app/core/langgraph/workflow/templates/` 目录创建 YAML 文件：

```yaml
name: my_workflow
description: "自定义工作流描述"
steps:
  - id: step_1
    worker: researcher
    task: "第一步任务描述"
    depends_on: []
  - id: step_2
    worker: coder
    task: "第二步任务描述"
    depends_on: [step_1]
```

模板在应用启动时自动加载。`depends_on: []` 的步骤会并行执行，有依赖的步骤按轮次顺序执行。

> 详细架构、调用链和日志事件请参阅 [NEW_FEATURES_GUIDE.md 第 14 章](./NEW_FEATURES_GUIDE.md#14-workflow-编排引擎)。

---

## 17. 常见问题

### Q: 如何添加新的 Agent 工具？

在 `app/core/langgraph/tools/` 目录下创建新工具：

```python
from langchain_core.tools import tool

@tool
def my_new_tool(query: str) -> str:
    """工具描述"""
    # 实现逻辑
    return result
```

然后在 `__init__.py` 中注册。

### Q: 如何添加新的 Skill（技能）？

**手动方式**：在 `app/core/skills/prompts/` 目录下创建 `.md` 文件，使用 YAML frontmatter 格式定义 `name`、`description` 和 `tags`，文件体为技能的详细内容。应用重启后自动加载。

**自动方式（SkillCreator）**：在对话中告诉 Agent "帮我创建一个关于 XX 的技能"，Agent 会调用 `create_skill` 工具，由 LLM 自动生成技能并持久化到 `prompts/_auto/` 目录，无需重启。后续可通过 `update_skill` 增量更新。

### Q: SkillCreator 自动生成的技能存放在哪里？

自动生成的技能存放在 `app/core/skills/prompts/_auto/` 目录，以 `{skill_name}.md` 命名。应用重启时 `SkillRegistry` 会自动扫描加载。可通过 `skill_registry.unregister(name)` 同时从内存和文件中删除。

### Q: 如何连接 MCP 服务器？

编辑项目根目录的 `mcp_servers.json`，添加服务器配置并将 `enabled` 设为 `true`。支持 SSE 和 stdio 两种传输方式。

### Q: 如何修改系统提示词？

编辑 `app/core/prompts/system.md` 文件。Skills 描述会通过 `{skills_prompt}` 占位符自动注入。

### Q: 如何添加新的 LLM 模型？

在 `app/services/llm.py` 的 `LLMRegistry.LLMS` 列表中添加配置。

### Q: 如何配置 RAG 知识库？

编辑项目根目录的 `rag_providers.json`，添加 Provider 配置并将 `enabled` 设为 `true`。内置支持 Qdrant、pgvector、RAGFlow 和通用 HTTP 四种 Provider 类型。无需修改代码，重启应用即可生效。

### Q: Windows 上 `make dev` 报错 `uvloop` 不可用？

Windows 不支持 `uvloop`。请使用项目根目录的 `run.py`：

```bash
python run.py
```

它会自动切换到 `WindowsSelectorEventLoopPolicy` 以兼容 `psycopg`。

### Q: 如何使用国内 LLM API？

设置 `OPENAI_API_BASE` 为兼容 OpenAI 协议的 API 地址：

```bash
OPENAI_API_BASE=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-your-deepseek-key
DEFAULT_LLM_MODEL=deepseek-chat
```

### Q: 前端无法连接后端？

- **本地开发**：确保后端运行在 `8000` 端口，前端 Vite 会自动代理 `/api` 请求
- **Docker 部署**：前端通过 Nginx 反向代理连接后端，确认 `docker-compose.yml` 中 `app` 服务正常运行

---

## 18. 总结

本项目提供了一个功能完整的 AI Agent 应用模板，包含：

- ✅ 生产级 API 架构
- ✅ LangGraph 状态化工作流
- ✅ **V1 Agent — LangChain `create_agent` + Middleware 模式**
- ✅ 长期记忆系统
- ✅ 完整的认证授权
- ✅ 可观测性支持
- ✅ Docker 容器化
- ✅ 模型评估框架
- ✅ Skills 渐进式技能加载
- ✅ **SkillCreator — LLM 自动创建 Skill + 增量学习（对话提取/指令生成/版本管理/持久化）**
- ✅ MCP 协议集成
- ✅ Multi-Agent Supervisor + Worker 架构（V1 handoff tools 实现）
- ✅ Human-in-the-Loop 人工审批机制（V1 Middleware 实现）
- ✅ **RAG 知识库 — 可插拔 Provider 架构（Qdrant / pgvector / RAGFlow / HTTP）**
- ✅ React 前端界面（聊天 + 登录 + 审批 + 国际化 + **会话侧栏** + **Markdown 渲染** + **401 全局拦截** + **代码分割** + **连接恢复**）
- ✅ **Workflow 编排引擎 — Orchestrator-Worker + Send API 多步并行工作流**

适用于快速构建企业级 AI 聊天机器人和智能助手应用。

> 更多详情请参考：[QUICK_START.md](./QUICK_START.md) | [NEW_FEATURES_GUIDE.md](./NEW_FEATURES_GUIDE.md) | [AGENTS.md](../AGENTS.md)
