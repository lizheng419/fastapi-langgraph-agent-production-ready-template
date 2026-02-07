# 新增功能详细技术文档

> 本文档覆盖项目所有模块的完整技术细节，包括 **Skills 系统**、**MCP 集成**、**Multi-Agent 多智能体架构**、**Human-in-the-Loop 人工审批**、**前端界面**、**V1 新版 Agent（LangChain v1 create_agent + Middleware）**、**RAG 知识库**、**Workflow 编排引擎**、**模型评估框架**、**数据库 ORM 模型**、**Prometheus 指标采集**、**Grafana 监控仪表板**，以及它们之间的协作关系、调用链、自定义扩展方式和最佳实践。

---

## 目录

1. [架构总览](#1-架构总览)
2. [Skills 渐进式技能加载系统](#2-skills-渐进式技能加载系统)
3. [MCP 协议集成](#3-mcp-协议集成)
4. [Agent 模式总览](#4-agent-模式总览)
5. [Human-in-the-Loop 人工审批机制](#5-human-in-the-loop-人工审批机制)
6. [前端界面](#6-前端界面)
7. [模块协作与完整调用链](#7-模块协作与完整调用链)
8. [安全设计](#8-安全设计)
9. [可观测性与日志](#9-可观测性与日志)
10. [测试指南](#10-测试指南)
11. [部署注意事项](#11-部署注意事项)
12. [常见问题 FAQ](#12-常见问题-faq)
13. [RAG 知识库集成](#13-rag-知识库集成)
14. [前端连接恢复机制](#14-前端连接恢复机制)
15. [模型评估框架](#15-模型评估框架)
16. [数据库 ORM 模型](#16-数据库-orm-模型)
17. [Prometheus 指标采集](#17-prometheus-指标采集)
18. [Grafana 监控仪表板](#18-grafana-监控仪表板)

---

## 1. 架构总览

### 1.1 新增模块全景图

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 React UI                            │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐     │
│  │ LoginPage│  │   ChatPage   │  │    ApprovalsPage      │     │
│  └────┬─────┘  └──────┬───────┘  └──────────┬────────────┘     │
│       │               │                     │                   │
│       └───────────────┼─────────────────────┘                   │
│                       │  HTTP / SSE                             │
└───────────────────────┼─────────────────────────────────────────┘
                        ▼
┌───────────────────────────────────────────────────────────────────┐
│                    FastAPI Backend (app/)                          │
│                                                                   │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ auth.py  │  │ chatbot.py   │  │     approval.py          │   │
│  │ (认证)   │  │ (聊天API)    │  │  (HITL 审批 API)         │   │
│  └──────────┘  └──────┬───────┘  └──────────┬───────────────┘   │
│                       │                      │                    │
│                       ▼                      ▼                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              V1Agent / V1MultiAgent / WorkflowGraph         │  │
│  │  ┌───────────┐  ┌────────┐  ┌──────────┐  ┌───────────┐  │  │
│  │  │ Supervisor│→ │ Worker │→ │ ToolCall │→ │ Approval  │  │  │
│  │  │   Node    │  │  Node  │  │   Node   │  │   Check   │  │  │
│  │  └───────────┘  └────────┘  └──────────┘  └───────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                       │                                          │
│          ┌────────────┼──────────────┬──────────────┐            │
│          ▼            ▼              ▼              ▼             │
│  ┌──────────────┐ ┌────────┐ ┌────────────┐ ┌────────────────┐ │
│  │ Skills 系统  │ │  MCP   │ │  内置工具  │ │  RAG 知识库    │ │
│  │ (按需加载)   │ │ (外部) │ │ (DuckDuckGo)│ │ (多源检索)    │ │
│  └──────────────┘ └────────┘ └────────────┘ └───────┬────────┘ │
│                                                      │          │
│                                    ┌─────────────────┼────────┐ │
│                                    ▼        ▼        ▼        │ │
│                                 Qdrant  pgvector  RAGFlow     │ │
│                                 (向量)  (PostgreSQL) (HTTP)   │ │
│                                    └─────────────────┘        │ │
└───────────────────────────────────────────────────────────────────┘
```

### 1.2 新增文件清单

| 模块 | 文件路径 | 说明 |
|------|----------|------|
| Skills | `app/core/skills/schema.py` | Skill Pydantic 数据模型 |
| Skills | `app/core/skills/registry.py` | SkillRegistry 注册表 + `load_skill` 工具 |
| Skills | `app/core/skills/__init__.py` | 模块导出 |
| Skills | `app/core/skills/prompts/*.md` | 预置技能 Markdown 文件 |
| MCP | `app/core/mcp/client.py` | MCPManager 客户端管理器 |
| MCP | `app/core/mcp/__init__.py` | 模块导出 |
| MCP | `mcp_servers.json` | MCP 服务器配置文件 |
| Multi-Agent | `app/core/langgraph/agents/supervisor.py` | Supervisor 路由 Agent |
| Multi-Agent | `app/core/langgraph/agents/workers.py` | Worker Agent 基类与专业实现 |
| Multi-Agent | `app/core/langgraph/agents/__init__.py` | 模块导出 |
| Multi-Agent | `app/core/langgraph/multi_agent_graph.py` | 完整的 Multi-Agent LangGraph 工作流 |
| HITL | `app/core/langgraph/hitl/manager.py` | ApprovalManager 审批管理器 |
| HITL | `app/core/langgraph/hitl/__init__.py` | 模块导出 |
| HITL | `app/schemas/approval.py` | 审批请求/响应 Pydantic 模型 |
| HITL | `app/api/v1/approval.py` | 审批 REST API 端点 |
| Frontend | `frontend/src/App.jsx` | 路由 + 全局认证状态 + 401 自动登出 |
| Frontend | `frontend/src/api.js` | 后端 API 封装层（全局 401 拦截） |
| Frontend | `frontend/src/components/MarkdownRenderer.jsx` | Markdown 渲染组件（GFM + 代码高亮 + Copy） |
| Frontend | `frontend/src/pages/LoginPage.jsx` | 登录/注册页面 |
| Frontend | `frontend/src/pages/ChatPage.jsx` | 聊天页面（SSE 流式 + 会话侧栏 + Markdown 渲染） |
| Frontend | `frontend/src/pages/ApprovalsPage.jsx` | HITL 审批管理页面 |
| Frontend | `frontend/src/i18n/` | 国际化配置（i18n 语言包） |
| Frontend | `frontend/Dockerfile` | 多阶段构建（node build + nginx 部署） |
| SkillCreator | `app/core/skills/creator.py` | SkillCreator（LLM 自动创建/增量学习 Skill） |
| SkillCreator | `app/core/skills/prompts/_auto/` | 自动生成 Skill 持久化目录 |
| Workflow | `app/core/langgraph/workflow/schema.py` | Workflow 数据模型（WorkflowStep, WorkflowPlan, WorkflowState） |
| Workflow | `app/core/langgraph/workflow/planner.py` | WorkflowPlanner（YAML 模板匹配 + LLM 动态规划） |
| Workflow | `app/core/langgraph/workflow/templates.py` | WorkflowTemplateRegistry（YAML 模板加载器） |
| Workflow | `app/core/langgraph/workflow/graph.py` | WorkflowGraph（Orchestrator-Worker + Send API） |
| Workflow | `app/core/langgraph/workflow/templates/*.yaml` | 预置 Workflow YAML 模板 |
| Workflow | `app/api/v1/chatbot_workflow.py` | Workflow API 端点 |
| RAG | `app/core/rag/__init__.py` | RAG 模块导出 |
| RAG | `app/core/rag/schema.py` | RAGDocument, RetrievalQuery, RetrievalResult 数据模型 |
| RAG | `app/core/rag/base.py` | BaseRetriever 抽象基类（Provider 接口） |
| RAG | `app/core/rag/manager.py` | RetrieverManager（注册、并行检索、结果合并去重） |
| RAG | `app/core/rag/providers/__init__.py` | PROVIDER_REGISTRY（Provider 类型 → 类映射） |
| RAG | `app/core/rag/providers/qdrant.py` | QdrantRetriever（Qdrant 向量数据库） |
| RAG | `app/core/rag/providers/pgvector.py` | PgvectorRetriever（PostgreSQL pgvector） |
| RAG | `app/core/rag/providers/ragflow.py` | RAGFlowRetriever（RAGFlow + OpenAI 兼容 API） |
| RAG | `app/core/rag/providers/http.py` | GenericHTTPRetriever（Dify / FastGPT / 自定义 REST） |
| RAG | `app/core/langgraph/tools/rag_retrieve.py` | `retrieve_knowledge` Agent 工具 |
| RAG | `rag_providers.json` | RAG Provider JSON 配置文件 |

### 1.3 修改的已有文件

| 文件 | 修改内容 |
|------|----------|
| `app/core/langgraph/graph.py` | 添加 MCP 工具异步初始化 (`_initialize_mcp_tools`) |
| `app/core/langgraph/tools/__init__.py` | 注册 `load_skill_tool`、`create_skill_tool`、`update_skill_tool`、`list_all_skills_tool` |
| `app/core/skills/schema.py` | 扩展 Skill 模型（version/source/auto_generated/timestamps） |
| `app/core/skills/registry.py` | 增强注册中心（_auto 持久化、增量更新、unregister） |
| `app/core/skills/__init__.py` | 导出 SkillCreator 和新工具 |
| `app/core/prompts/system.md` | 添加 `{skills_prompt}` 占位符 |
| `app/core/prompts/__init__.py` | 注入 Skills 描述到系统提示词 |
| `app/api/v1/api.py` | 注册 `/approvals` 和 `/chatbot/workflow` 路由 |
| `frontend/src/api.js` | 重构 `sendMessage`/`streamMessage` 支持动态 Agent 模式 URL 路由；添加全局 401 拦截（`handleResponse`）；新增 `deleteSession`、`getMessages(mode)` |
| `frontend/src/App.jsx` | 集成 `setAuthErrorHandler` 实现全局 401 自动登出 |
| `frontend/src/pages/ChatPage.jsx` | 新增会话侧栏（列表/切换/删除/新建）、Agent 模式选择器、Workflow 模板选择器、集成 MarkdownRenderer、页面加载时拉取消息历史 |
| `frontend/src/i18n/zh.json` | 新增 Agent 模式切换 + sidebar 相关 i18n 词条 |
| `frontend/src/i18n/en.json` | 新增 Agent 模式切换 + sidebar 相关 i18n 词条 |
| `frontend/vite.config.js` | 新增 `manualChunks` 代码分割（react-vendor / markdown / syntax-highlighter） |
| `frontend/package.json` | 新增 `react-markdown`、`remark-gfm`、`react-syntax-highlighter` 依赖 |
| `app/core/config.py` | 添加 `approvals` 速率限制配置 |
| `pyproject.toml` | 添加 `langchain-mcp-adapters`、`mcp`、`pytest-asyncio`、`pyyaml` 依赖 |
| `.env.example` | 添加 MCP 配置说明 |
| `app/core/langgraph/tools/__init__.py` | 注册 `retrieve_knowledge` RAG 检索工具 |
| `app/core/config.py` | 新增 `QDRANT_*` 配置项（替代旧 `MEMORY_POSTGRES_*`） |
| `docker-compose.yml` | 新增 Qdrant 服务、挂载 `rag_providers.json`、移除旧 `mem0-db` |
| `schema.sql` | mem0 pgvector 表（`langchain_pg_collection` / `langchain_pg_embedding`）合并到主库 |
| `pyproject.toml` | 新增 `qdrant-client`、`httpx`、`langchain-postgres`、`asyncpg` 依赖 |
| `.env` / `.env.example` | 新增 `QDRANT_HOST` / `QDRANT_PORT` / `QDRANT_API_KEY` 等变量 |
| `frontend/src/api.js` | 新增 `safeFetch` 网络错误包装、`isNetworkError` 工具函数、`validateToken` API、401 防抖、修复 `streamMessage` 双重 `onDone` |
| `frontend/src/App.jsx` | 启动时 `validateToken` 验证 localStorage token 有效性、loading spinner |
| `frontend/src/pages/ChatPage.jsx` | `connectionError` 状态 + 黄色 banner + 每 5s 自动重试 + 手动重试按钮 |
| `frontend/src/pages/ApprovalsPage.jsx` | 网络错误检测 + 连接错误 banner |
| `frontend/src/i18n/zh.json` / `en.json` | 新增 `connectionError`、`retry` i18n 词条 |

---

## 2. Skills 渐进式技能加载系统

### 2.1 功能概述

Skills 系统实现了 **渐进式披露（Progressive Disclosure）** 模式。Agent 的 system prompt 中只包含每个技能的简短描述（约 1-2 句话），完整的技能指令通过 `load_skill` 工具按需加载。这解决了以下问题：

- **上下文窗口浪费**：避免将所有技能详情一次性塞入 system prompt
- **可扩展性**：技能数量增加不会线性增长 prompt token 消耗
- **模块化管理**：每个技能是独立的 Markdown 文件，易于维护

### 2.2 核心类与函数

#### `Skill` — 数据模型

```
文件: app/core/skills/schema.py
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 唯一标识符，如 `"sql_query"` |
| `description` | `str` | 简短描述，注入到 system prompt |
| `content` | `str` | 完整技能内容，通过 `load_skill` 工具加载 |
| `tags` | `List[str]` | 分类标签，用于组织和发现 |
| `version` | `int` | 技能版本号，增量更新时自动递增 |
| `source` | `str` | 来源：`manual`（手动）、`conversation`（对话提取）、`agent`（Agent 创建） |
| `auto_generated` | `bool` | 是否由 SkillCreator 自动生成 |
| `created_at` | `Optional[datetime]` | 创建时间戳 |
| `updated_at` | `Optional[datetime]` | 最后更新时间戳 |

#### `SkillRegistry` — 技能注册表

```
文件: app/core/skills/registry.py
```

| 方法 | 签名 | 说明 |
|------|------|------|
| `__init__` | `() -> None` | 初始化并扫描 `prompts/` 和 `prompts/_auto/` 目录 |
| `_load_skills_from_prompts` | `() -> None` | 加载手动 + 自动生成的技能 |
| `_load_skills_from_directory` | `(directory, source) -> None` | 从指定目录加载技能文件 |
| `_parse_skill_file` | `(filepath, default_source) -> Optional[Skill]` | 解析 YAML frontmatter + Markdown body |
| `register` | `(skill: Skill) -> None` | 编程方式注册技能 |
| `register_or_update` | `(skill, persist) -> Skill` | 注册或增量更新技能（自动版本递增+持久化） |
| `unregister` | `(name: str) -> bool` | 移除技能（含自动删除 _auto/ 文件） |
| `_save_skill_to_file` | `(skill: Skill) -> None` | 持久化到 `prompts/_auto/` 目录 |
| `get` | `(name: str) -> Optional[Skill]` | 按名称获取技能 |
| `list_skills` | `() -> List[Skill]` | 列出所有已注册技能 |
| `get_skills_prompt` | `() -> str` | 生成注入 system prompt 的技能描述段 |

#### Agent 工具

| 工具 | 说明 |
|------|------|
| `load_skill(skill_name)` | 按名称加载技能全文内容 |
| `create_skill(instruction)` | 从指令/描述自动创建新技能（LLM 驱动） |
| `update_skill(skill_name, new_info)` | 增量更新已有技能，合并新知识 |
| `list_all_skills()` | 列出所有技能及版本、来源信息 |

### 2.3 调用链

```
应用启动
  │
  ├─→ SkillRegistry.__init__()
  │     └─→ _load_skills_from_prompts()
  │           └─→ 遍历 app/core/skills/prompts/*.md
  │                 └─→ _parse_skill_file(filepath) → Skill 对象
  │                       └─→ self._skills[name] = skill
  │
  ├─→ app/core/prompts/__init__.py: load_system_prompt()
  │     └─→ skill_registry.get_skills_prompt()
  │           └─→ 生成 "## Available Skills\n- skill1: desc\n- skill2: desc"
  │     └─→ system.md.format(skills_prompt=skills_prompt)
  │
  └─→ Agent 对话中
        └─→ LLM 决定需要某个技能
              └─→ 调用 load_skill("sql_query")
                    └─→ skill_registry.get("sql_query")
                          └─→ 返回 skill.content (完整指令)
```

### 2.4 Skill Markdown 文件格式

```markdown
---
name: sql_query
description: Expert guidelines for writing safe, optimized SQL queries
tags: sql, database, query
---

# SQL Query Expert

## Guidelines
1. Always use parameterized queries
2. Validate all user inputs
...
```

**规则**：
- 文件必须以 `---` 开始（YAML frontmatter）
- `name` 和 `description` 为必填字段
- `tags` 为可选，逗号分隔
- frontmatter 之后的所有内容为技能正文

### 2.5 自定义：添加新技能

**步骤 1**：在 `app/core/skills/prompts/` 目录创建 `.md` 文件

```markdown
---
name: kubernetes_ops
description: Guidelines for Kubernetes cluster operations and troubleshooting
tags: kubernetes, devops, infrastructure
---

# Kubernetes Operations

## Diagnostic Commands
- kubectl get pods -A
- kubectl describe pod <name>
...
```

**步骤 2**：重启应用，`SkillRegistry` 自动加载

**步骤 3**（可选）：编程注册

```python
from app.core.skills import skill_registry, Skill

skill_registry.register(Skill(
    name="my_custom_skill",
    description="My custom specialist instructions",
    content="Full content here...",
    tags=["custom"],
))
```

### 2.6 SkillCreator — LLM 自动创建与增量学习

```text
文件: app/core/skills/creator.py
```

**SkillCreator** 是基于 [skills.sh/anthropics/skills/skill-creator](https://skills.sh/anthropics/skills/skill-creator) 理念实现的 LLM 驱动技能自动生成器。它让 Agent 在对话过程中**自动发现、提取并持久化可复用知识**，实现真正的增量学习。

#### 2.6.1 核心能力

| 类/方法 | 签名 | 说明 |
|---------|------|------|
| `SkillCreator` | `class` | LLM 驱动的技能生成器（全局单例 `skill_creator`） |
| `create_from_instruction` | `async (instruction, source) -> Optional[Skill]` | 从用户指令/描述自动生成 Skill |
| `create_from_conversation` | `async (messages, source) -> Optional[Skill]` | 分析对话历史，提取可复用知识生成 Skill |
| `update_skill` | `async (existing_skill, new_info) -> Optional[Skill]` | 增量更新：将新知识合并到已有 Skill，保留原有结构 |
| `_parse_skill_response` | `(response, source) -> Optional[Skill]` | 解析 LLM 输出的 YAML frontmatter + Markdown 为 Skill 对象 |

#### 2.6.2 Agent 工具（对话中使用）

Agent 在对话中通过以下 `@tool` 工具触发 SkillCreator：

| 工具函数 | 参数 | 触发场景 |
|----------|------|----------|
| `create_skill(instruction)` | `instruction: str` | 用户说 "学会这个"、"记住这个模式"、"创建一个 XX 技能" |
| `update_skill(skill_name, new_info)` | `skill_name: str, new_info: str` | "更新 XX 技能"、发现新模式需要合并到已有技能 |
| `list_all_skills()` | 无参数 | "列出所有技能"、"有哪些技能" |

#### 2.6.3 使用场景

**场景 1：用户主动要求创建技能**

```text
用户: 帮我创建一个专门处理 PostgreSQL 查询优化的技能，包括索引策略、EXPLAIN 分析、慢查询排查

Agent 内部调用: create_skill("专门处理 PostgreSQL 查询优化的技能，包括索引策略、EXPLAIN 分析、慢查询排查")
       │
       ▼
SkillCreator.create_from_instruction(instruction, source="agent")
       │  LLM 分析指令 → 生成 YAML frontmatter + Markdown 技能内容
       ▼
SkillRegistry.register_or_update(skill, persist=True)
       │  保存到 prompts/_auto/postgresql_optimization.md
       ▼
Agent 回复: "技能 'postgresql_optimization' 创建成功 (v1)。
            描述: PostgreSQL 查询优化专家...
            标签: postgresql, optimization, database
            可通过 load_skill('postgresql_optimization') 使用。"
```

**场景 2：增量更新已有技能**

```text
用户: 更新 postgresql_optimization 技能，加上 pg_stat_statements 监控和连接池调优策略

Agent 内部调用: update_skill("postgresql_optimization", "pg_stat_statements 监控和连接池调优策略")
       │
       ▼
SkillCreator.update_skill(existing_skill, new_info)
       │  LLM 读取原有内容 → 智能合并新知识 → 保留原结构
       │  version: 1 → 2, updated_at 更新
       ▼
SkillRegistry.register_or_update(updated_skill, persist=True)
       │  覆盖写入 prompts/_auto/postgresql_optimization.md
       ▼
Agent 回复: "技能 'postgresql_optimization' 已更新至 v2。"
```

**场景 3：从对话历史提取知识（编程调用）**

```python
from app.core.skills import skill_creator, skill_registry
from langchain_core.messages import HumanMessage, AIMessage

# 假设有一段关于 Docker 部署最佳实践的对话
messages = [
    HumanMessage(content="Docker 多阶段构建怎么优化镜像大小？"),
    AIMessage(content="1. 使用 alpine 基础镜像...\n2. 分离构建和运行阶段...\n3. 使用 .dockerignore..."),
    HumanMessage(content="生产环境的健康检查怎么配？"),
    AIMessage(content="在 Dockerfile 中添加 HEALTHCHECK..."),
]

# 从对话中提取可复用知识
skill = await skill_creator.create_from_conversation(messages, source="conversation")
if skill:
    # 注册并持久化
    skill_registry.register_or_update(skill, persist=True)
    print(f"提取技能: {skill.name} — {skill.description}")
```

#### 2.6.4 完整工作流程

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                     SkillCreator 工作流程                                 │
│                                                                         │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  触发来源        │    │  SkillCreator    │    │  SkillRegistry   │  │
│  │                  │    │                  │    │                  │  │
│  │ • 用户指令       │──→ │ create_from_     │──→ │ register_or_     │  │
│  │   "创建技能..."  │    │   instruction()  │    │   update()       │  │
│  │                  │    │                  │    │   ├─ 版本递增    │  │
│  │ • 对话提取       │──→ │ create_from_     │    │   └─ 持久化      │  │
│  │   (编程调用)     │    │   conversation() │    │     _auto/*.md   │  │
│  │                  │    │                  │    │                  │  │
│  │ • 增量更新       │──→ │ update_skill()   │    │                  │  │
│  │   "更新技能..."  │    │                  │    │                  │  │
│  └──────────────────┘    └────────┬─────────┘    └──────────────────┘  │
│                                   │                                     │
│                          ┌────────▼─────────┐                          │
│                          │  LLM Service     │                          │
│                          │  ainvoke()       │                          │
│                          │  • 分析输入       │                          │
│                          │  • 生成 YAML+MD  │                          │
│                          │  • 解析为 Skill   │                          │
│                          └──────────────────┘                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    应用重启时 _auto/ 目录自动加载
                    → 下次对话 system prompt 自动包含新技能描述
                    → Agent 可通过 load_skill() 加载完整内容
```

#### 2.6.5 自动生成文件格式

自动创建的 Skill 持久化到 `app/core/skills/prompts/_auto/` 目录：

```markdown
---
name: postgresql_optimization
description: PostgreSQL 查询优化专家，提供索引策略、EXPLAIN 分析和慢查询排查指南
tags: postgresql, optimization, database
version: 2
source: agent
auto_generated: true
---

# PostgreSQL Optimization

## 索引策略
1. 为高频查询的 WHERE/JOIN 列创建索引
2. 使用复合索引覆盖多条件查询
...

## EXPLAIN 分析
- 始终使用 `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)`
- 关注 Seq Scan → 考虑添加索引
...
```

**文件生命周期**：

| 阶段 | 行为 |
|------|------|
| 首次创建 | `_save_skill_to_file()` 写入 `prompts/_auto/{name}.md` |
| 增量更新 | 覆盖写入同名文件，`version` 递增，`updated_at` 更新 |
| 应用重启 | `SkillRegistry.__init__()` 自动扫描 `_auto/` 目录加载 |
| 手动删除 | `skill_registry.unregister(name)` 同时删除内存和文件 |

#### 2.6.6 SkillCreator 内部 Prompt 设计

SkillCreator 使用精心设计的 system prompt 驱动 LLM 生成高质量技能：

| Prompt 常量 | 用途 |
|-------------|------|
| `SKILL_CREATE_SYSTEM_PROMPT` | 指导 LLM 如何从指令/描述生成规范的 Skill（YAML + Markdown 格式） |
| `SKILL_CREATE_USER_PROMPT` | 包装用户输入（指令 or 对话内容）为 LLM 请求 |
| `SKILL_UPDATE_SYSTEM_PROMPT` | 指导 LLM 进行增量合并：保留已有内容 + 添加新知识 + 移除过时信息 |
| `SKILL_UPDATE_USER_PROMPT` | 传递已有 Skill 完整内容 + 新信息给 LLM |
| `SKILL_FROM_CONVERSATION_PROMPT` | 指导 LLM 从对话历史中提取可复用知识（支持 `NO_SKILL_FOUND` 回退） |

**核心设计原则**（来自 skills.sh）：

- **Concise is key** — 上下文窗口是共享资源，每个段落都要值得其 token 消耗
- **Non-obvious only** — 只记录 AI 不已知的领域知识
- **Concrete examples** — 优先使用具体示例而非抽象描述
- **Imperative form** — 使用祈使句/不定式形式编写指令

#### 2.6.7 最佳实践

1. **让 Agent 自然触发**：在对话中说 "学会这个"、"记住这个模式"、"创建一个 XX 技能"，Agent 会自动调用 `create_skill`
2. **渐进式完善**：先创建基础技能，后续通过 `update_skill` 不断合并新知识
3. **定期清理**：使用 `list_all_skills()` 检查技能列表，通过 `skill_registry.unregister()` 移除过时技能
4. **手动 vs 自动**：核心技能建议手动维护在 `prompts/` 目录；实验性或快速迭代的技能使用自动生成
5. **版本追踪**：每次 `update_skill` 自动递增版本号，可通过 `list_all_skills()` 查看各技能版本

---

## 3. MCP 协议集成

### 3.1 功能概述

**Model Context Protocol (MCP)** 是连接 AI 系统与外部工具和数据源的标准协议。本集成允许 Agent 动态连接外部 MCP 服务器（如数据库、文件系统、API 网关），自动将其工具转换为 LangChain 兼容格式。

### 3.2 核心类与函数

#### `MCPServerConfig` — 服务器配置

```
文件: app/core/mcp/client.py
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 服务器名称 |
| `transport` | `str` | 传输方式：`"sse"` 或 `"stdio"` |
| `url` | `Optional[str]` | SSE 传输的服务器 URL |
| `command` | `Optional[str]` | stdio 传输的启动命令 |
| `args` | `List[str]` | stdio 命令参数 |
| `env` | `Dict[str, str]` | stdio 环境变量 |
| `enabled` | `bool` | 是否启用 |

#### `MCPManager` — 客户端管理器

| 方法 | 签名 | 说明 |
|------|------|------|
| `__init__` | `() -> None` | 初始化并加载 `mcp_servers.json` |
| `_load_config` | `() -> None` | 解析配置文件，创建 `MCPServerConfig` 列表 |
| `initialize` | `async () -> None` | 异步连接所有已启用的 MCP 服务器 |
| `_connect_server` | `async (server) -> None` | 连接单个服务器并加载其工具 |
| `get_tools` | `() -> List[BaseTool]` | 获取所有已加载的 MCP 工具 |

#### `get_mcp_tools` — 便捷函数

```python
async def get_mcp_tools() -> List[BaseTool]
```

自动初始化 MCPManager 并返回所有可用工具，供 `V1Agent` / `V1MultiAgent` 的 `_initialize_mcp_tools()` 调用。

### 3.3 调用链

```
应用启动
  │
  ├─→ MCPManager.__init__()
  │     └─→ _load_config()
  │           └─→ 读取 mcp_servers.json
  │                 └─→ 过滤 enabled=true 的服务器
  │
  └─→ V1Agent / V1MultiAgent
        └─→ _initialize_mcp_tools()
              └─→ get_mcp_tools()
                    └─→ mcp_manager.initialize()
                          └─→ 对每个服务器: _connect_server(server)
                                ├─→ [SSE] sse_client(url) → ClientSession → load_mcp_tools
                                └─→ [stdio] stdio_client(params) → ClientSession → load_mcp_tools
                    └─→ mcp_manager.get_tools() → List[BaseTool]
              └─→ self._all_tools.extend(mcp_tools)
              └─→ self.llm_service.bind_tools(self._all_tools)
```

### 3.4 配置文件格式

```json
{
  "servers": [
    {
      "name": "filesystem",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"],
      "enabled": true
    },
    {
      "name": "my-api",
      "transport": "sse",
      "url": "http://localhost:8080/sse",
      "enabled": false
    }
  ]
}
```

### 3.5 自定义：添加新 MCP 服务器

1. 编辑项目根目录 `mcp_servers.json`
2. 在 `servers` 数组中添加配置项
3. 设置 `enabled: true`
4. 重启应用

**SSE 方式**需提供 `url`，**stdio 方式**需提供 `command` 和可选的 `args`/`env`。

### 3.6 依赖

```toml
# pyproject.toml
"langchain-mcp-adapters>=0.2.0"
"mcp>=1.20.0"
```

---

## 4. Agent 模式总览

本项目支持 **4 种 Agent 运行模式**，每种模式有独立的架构、API 端点和适用场景。详细的实现原理、函数调用链、使用示例和扩展指南请参阅各模式的专属文档。
### 4.1 模式一览

| 模式 | 实现类 | API 前缀 | 核心机制 | 详细文档 |
|------|--------|---------|---------|---------|
| **Single** | `V1Agent` | `/chatbot` | `create_agent` + Middleware 栈 | [AGENT_MODE_2_V1_SINGLE.md](./AGENT_MODE_2_V1_SINGLE.md) |
| **Multi** | `V1MultiAgent` | `/chatbot?mode=multi` | Supervisor + handoff tools + Workers | [AGENT_MODE_3_V1_MULTI.md](./AGENT_MODE_3_V1_MULTI.md) |
| **Workflow** | `WorkflowGraph` | `/chatbot/workflow` | Orchestrator-Worker + Send API 并行 | [AGENT_MODE_4_WORKFLOW.md](./AGENT_MODE_4_WORKFLOW.md) |

### 4.2 模式选择指南

| 场景 | 推荐模式 | 原因 |
|------|---------|------|
| 全新项目、快速原型 | **V1 Single** | Middleware 简洁，一行启用 HITL/追踪/记忆 |
| 需要高度自定义图节点 | **V1 Multi** | Supervisor handoff tools 自动路由 |
| 需要专家路由（研究/编码/分析） | **V1 Multi** | Supervisor handoff tools 自动路由 |
| 复杂多步骤任务、并行执行 | **Workflow** | Send API 并行 + 依赖链调度 + YAML 模板 |
| 已上线旧版部署 | **V1 Single** | 稳定运行，无迁移风险 |

### 4.3 架构对比

```text
V1 Single: 用户 → create_agent (Middleware 栈自动处理循环)    → END
V1 Multi:  用户 → Supervisor → handoff tool → Worker Agent   → END
Workflow:  用户 → Planner → Send×N (并行) → check → synthesizer → END
```

### 4.4 共享基础设施

四种模式共享以下基础设施，互不干扰：

- **工具集**：内置工具（DuckDuckGo、Skills）+ MCP 外部工具
- **Worker 注册表**：`WORKER_REGISTRY`（researcher、coder、analyst）
- **LLM 服务**：`LLMRegistry` / `LLMService`
- **长期记忆**：mem0 + pgvector
- **Checkpointing**：PostgreSQL `AsyncPostgresSaver`
- **Langfuse 追踪**：config callbacks 层统一注入

> **深入了解**：每种模式的函数调用链、Graph 构建细节、API 使用示例和扩展指南，请点击上方表格中的详细文档链接。

---

## 5. Human-in-the-Loop 人工审批机制

### 5.1 功能概述

HITL 机制在 Agent 执行敏感操作前自动中断执行，创建审批请求并等待人类审核。这是生产环境中的关键安全屏障，防止 Agent 自主执行破坏性操作。

### 5.2 审批状态机

```
                    ┌─────────┐
         创建       │ PENDING │  等待人工审核
         ─────────→ │         │
                    └────┬────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
        ┌──────────┐ ┌──────────┐ ┌─────────┐
        │ APPROVED │ │ REJECTED │ │ EXPIRED │
        │ (批准)   │ │ (拒绝)   │ │ (过期)  │
        └──────────┘ └──────────┘ └─────────┘
              │          │          │
              │    终态（不可逆）     │
              └──────────┴──────────┘
```

### 5.3 核心类与函数

#### `ApprovalStatus` — 状态枚举

| 值 | 说明 |
|----|------|
| `PENDING` | 等待审核 |
| `APPROVED` | 已批准 |
| `REJECTED` | 已拒绝 |
| `EXPIRED` | 超时过期（默认 1 小时） |

#### `ApprovalRequest` — 审批请求模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `str` | UUID，自动生成 |
| `session_id` | `str` | 所属会话 |
| `user_id` | `Optional[str]` | 发起用户 |
| `action_type` | `str` | 操作类型（如 `"tool_execution"`） |
| `action_description` | `str` | 人类可读的操作描述 |
| `action_data` | `Dict` | 操作参数详情 |
| `status` | `ApprovalStatus` | 当前状态 |
| `created_at` | `datetime` | 创建时间 |
| `resolved_at` | `Optional[datetime]` | 处理时间 |
| `reviewer_comment` | `Optional[str]` | 审核意见 |
| `expires_at` | `datetime` | 过期时间（默认创建后 1 小时） |

#### `ApprovalManager` — 审批管理器

| 方法 | 签名 | 说明 |
|------|------|------|
| `create_request` | `async (session_id, action_type, action_description, ...) -> ApprovalRequest` | 创建审批请求 + asyncio.Event |
| `wait_for_approval` | `async (request_id, timeout) -> ApprovalRequest` | 阻塞等待审批结果（Event.wait） |
| `approve` | `(request_id, comment) -> ApprovalRequest` | 批准请求，触发 Event.set() |
| `reject` | `(request_id, comment) -> ApprovalRequest` | 拒绝请求，触发 Event.set() |
| `get_request` | `(request_id) -> Optional[ApprovalRequest]` | 获取请求详情 |
| `get_pending_requests` | `(session_id) -> List[ApprovalRequest]` | 获取待审批列表（自动清理过期） |
| `cleanup_expired` | `() -> int` | 手动清理过期请求 |

**异步等待机制**：每个 `ApprovalRequest` 关联一个 `asyncio.Event`。当 `approve()` 或 `reject()` 被调用时，`Event.set()` 会唤醒等待中的协程。

### 5.4 API 端点

```
文件: app/api/v1/approval.py
路由前缀: /api/v1/approvals
```

| 方法 | 路径 | 限速 | 说明 |
|------|------|------|------|
| `GET` | `/pending` | 50/min | 获取当前会话的待审批列表 |
| `GET` | `/{request_id}` | 50/min | 获取单个审批请求详情 |
| `POST` | `/{request_id}/approve` | 20/min | 批准请求（可附评论） |
| `POST` | `/{request_id}/reject` | 20/min | 拒绝请求（可附评论） |

**请求体**（approve/reject）：

```json
{
  "comment": "Looks good, approved."
}
```

**响应体**：

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "session_id": "session-123",
  "user_id": "user-456",
  "action_type": "tool_execution",
  "action_description": "Agent wants to execute: delete_record",
  "action_data": {"tool_calls": "delete_record"},
  "status": "approved",
  "created_at": "2025-01-01T00:00:00",
  "resolved_at": "2025-01-01T00:01:30",
  "reviewer_comment": "Looks good, approved.",
  "expires_at": "2025-01-01T01:00:00"
}
```

**安全设计**：
- 所有端点需要 JWT 认证 (`get_current_session`)
- 会话隔离：只能操作自己会话的审批请求（`session_id` 校验）
- 速率限制：防止滥用

### 5.5 调用链

```
Agent tool_call 节点
  │
  ├─→ _requires_approval("delete_record", args)
  │     └─→ "delete" in tool_name.lower() → True
  │
  ├─→ goto "approval_check" 节点
  │     └─→ approval_manager.create_request(
  │           session_id, "tool_execution",
  │           "Agent wants to execute: delete_record",
  │           action_data={...}
  │         )
  │     └─→ 返回 ApprovalRequest(id="abc-123", status=PENDING)
  │     └─→ 更新 state: approval_request_id = "abc-123"
  │     └─→ goto END（暂停执行，等待人工干预）
  │
  └─→ 用户通过前端或 API 操作:
        │
        ├─→ POST /api/v1/approvals/abc-123/approve
        │     └─→ approval_manager.approve("abc-123", comment="OK")
        │           └─→ request.status = APPROVED
        │           └─→ asyncio.Event.set() → 唤醒等待协程
        │
        └─→ POST /api/v1/approvals/abc-123/reject
              └─→ approval_manager.reject("abc-123", comment="Too risky")
                    └─→ request.status = REJECTED
                    └─→ asyncio.Event.set()
```

### 5.6 敏感操作判定规则

`MultiAgentGraph._requires_approval()` 通过以下关键词模式匹配：

| 关键词 | 匹配示例 |
|--------|----------|
| `delete` | `delete_record`, `delete_file` |
| `modify` | `modify_config`, `modify_permission` |
| `update` | `update_database`, `update_user` |
| `write` | `write_file`, `write_to_disk` |
| `execute_sql` | `execute_sql_query` |
| `send_email` | `send_email_notification` |

### 5.7 自定义：修改审批规则

**方式 1**：修改关键词列表

```python
# multi_agent_graph.py
def _requires_approval(self, tool_name: str, args: dict) -> bool:
    sensitive_patterns = [
        "delete", "modify", "update", "write",
        "execute_sql", "send_email",
        "deploy",          # 新增
        "transfer_funds",  # 新增
    ]
    return any(pattern in tool_name.lower() for pattern in sensitive_patterns)
```

**方式 2**：基于参数的细粒度控制

```python
def _requires_approval(self, tool_name: str, args: dict) -> bool:
    # 金额超过 1000 才需审批
    if tool_name == "transfer_funds" and args.get("amount", 0) > 1000:
        return True
    # 生产环境操作需审批
    if args.get("environment") == "production":
        return True
    return False
```

---

## 6. 前端界面

### 6.1 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.3 | UI 框架 |
| Vite | 6.0 | 开发/构建工具（含 manualChunks 代码分割） |
| TailwindCSS | 3.4 | 原子化 CSS 框架 |
| React Router | 6.28 | 客户端路由 |
| Lucide React | 0.460 | SVG 图标库 |
| react-markdown | 10.1 | Markdown 渲染 |
| remark-gfm | 4.0 | GitHub Flavored Markdown 支持（表格、任务列表等） |
| react-syntax-highlighter | 16.1 | 代码块语法高亮 |

### 6.2 项目结构

```text
frontend/
├── index.html              # 入口 HTML
├── package.json            # 依赖配置
├── Dockerfile              # 多阶段构建（node:20-alpine build + nginx:alpine 部署）
├── vite.config.js          # Vite + API proxy + manualChunks 代码分割
├── tailwind.config.js      # TailwindCSS 配置
├── postcss.config.js       # PostCSS 配置
├── public/
│   └── vite.svg            # Favicon
└── src/
    ├── main.jsx            # React 入口
    ├── index.css           # 全局样式 + Tailwind 指令
    ├── App.jsx             # 路由 + 全局认证状态 + 401 自动登出
    ├── api.js              # 后端 API 封装层（全局 401 拦截）
    ├── components/
    │   └── MarkdownRenderer.jsx  # Markdown 渲染组件（GFM + 代码高亮 + Copy）
    ├── i18n/
    │   ├── LanguageContext.jsx    # i18n Context + useLanguage hook
    │   ├── zh.json               # 中文语言包
    │   └── en.json               # 英文语言包
    └── pages/
        ├── LoginPage.jsx         # 登录/注册
        ├── ChatPage.jsx          # 聊天（SSE 流式 + 会话侧栏 + Markdown 渲染）
        └── ApprovalsPage.jsx     # HITL 审批管理
```

### 6.3 页面详解

#### LoginPage — 登录/注册

**功能**：
- 登录/注册 Tab 切换
- 邮箱 + 密码表单验证
- 注册后自动登录 + 创建会话
- 错误提示
- 加载状态指示器

**认证流程**：

```
用户提交表单
  │
  ├─→ [注册] register(email, password)
  │     └─→ POST /api/v1/auth/register
  │     └─→ createSession(userToken)
  │           └─→ POST /api/v1/auth/session
  │     └─→ onAuth({ userToken, sessionToken, sessionId, email })
  │
  └─→ [登录] login(email, password)
        └─→ POST /api/v1/auth/login (OAuth2 form)
        └─→ createSession(accessToken)
        └─→ onAuth({ userToken, sessionToken, sessionId, email })
```

**状态持久化**：认证信息存储在 `localStorage`，刷新页面不丢失。

#### ChatPage — 聊天界面

**功能**：
- **SSE 流式响应**：逐字显示 AI 回复，实时感体验
- **会话侧栏**：可折叠的暗色侧栏，支持会话列表展示、切换、删除和新建会话
- **消息历史加载**：页面加载时自动拉取当前会话的历史消息
- **Markdown 渲染**：集成 `MarkdownRenderer` 组件，支持 GFM 表格、代码块语法高亮（Prism）、行内代码、引用块、链接等
- **代码块 Copy 按钮**：每个代码块右上角显示语言标签和一键复制按钮
- **Agent 模式选择器**：顶部栏下拉菜单，支持 4 种 Agent 模式切换（Legacy/V1 Single/V1 Multi/Workflow）
- **Workflow 模板选择**：Workflow 模式下额外显示模板下拉框
- **快捷建议**：空聊天时显示 4 个预设问题
- **审批入口**：导航到 Approvals 页面
- **自适应输入框**：支持多行输入，Enter 发送，Shift+Enter 换行
- **全局 401 拦截**：Session 过期时自动登出，通过 `api.js` 的 `handleResponse` 统一处理（含 401 防抖）
- **连接恢复**：后端不可达时显示黄色 banner + 每 5 秒自动重试 + 手动重试按钮，恢复后自动清除（详见 [Section 14](#14-前端连接恢复机制)）

**MarkdownRenderer 组件**（`components/MarkdownRenderer.jsx`）：
- 基于 `react-markdown` + `remark-gfm` 渲染 Markdown 内容
- 使用 `react-syntax-highlighter`（Prism + oneLight 主题）高亮代码块
- 自定义渲染：段落、标题（h1-h3）、列表、引用块、表格、链接、分割线
- 代码块顶部显示语言标签 + Copy/Copied 状态按钮

**会话侧栏**：
- 暗色主题（`bg-gray-900`），可通过按钮折叠/展开
- 侧栏状态持久化到 `localStorage`（`sidebarOpen` key）
- 显示所有会话列表，高亮当前活跃会话
- 支持切换会话（自动加载目标会话的历史消息）
- 支持删除会话（带确认提示，删除后自动切换到其他会话或创建新会话）
- 顶部 "New Chat" 按钮创建新会话

**流式消息处理**：

```text
用户发送消息
  │
  ▼
streamMessage(sessionToken, messages, onChunk, onDone, mode, template)
  │
  ├─→ POST /api/v1/chatbot/chat/stream   (根据 mode 动态构建 URL)
  │     └─→ SSE 响应: "data: {"content": "Hello"}\n"
  │
  ├─→ ReadableStream reader 逐块读取
  │     └─→ TextDecoder 解码
  │     └─→ 按 "\n" 分割行
  │     └─→ 解析 "data: " 前缀的 JSON
  │           ├─→ {content: "Hello"} → onChunk("Hello")
  │           └─→ {done: true} → onDone()
  │
  └─→ React state 实时更新最后一条 assistant 消息
       └─→ MarkdownRenderer 实时渲染 Markdown 内容
```

#### ApprovalsPage — HITL 审批管理

**功能**：
- **待审批列表**：自动每 10 秒轮询刷新
- **详情展示**：操作类型、描述、参数、时间信息
- **批准/拒绝**：一键操作，支持附加评论
- **空状态**：无待审批时显示 "All Clear" 提示
- **手动刷新**：刷新按钮
- **连接错误提示**：后端不可达时显示黄色 banner，10 秒轮询自动充当重试机制

### 6.4 API 封装层

```text
文件: frontend/src/api.js
```

**全局 401 拦截机制**：

`api.js` 实现了统一的 401 响应拦截和网络错误处理。通过 `setAuthErrorHandler(handler)` 注册回调（在 `App.jsx` 中设置为 `logout`），所有 API 调用通过 `safeFetch()` + `handleResponse()` 双层包装：网络不可达时抛出清晰错误，401 响应通过防抖机制避免多次触发 logout。

| 函数 | 说明 | 后端端点 |
|------|------|----------|
| `setAuthErrorHandler(handler)` | 注册全局 401 错误回调 | — |
| `register(email, password)` | 注册 | `POST /auth/register` |
| `login(username, password)` | 登录 (OAuth2) | `POST /auth/login` |
| `createSession(userToken)` | 创建会话 | `POST /auth/session` |
| `getSessions(userToken)` | 获取会话列表 | `GET /auth/sessions` |
| `deleteSession(sessionToken, sessionId)` | 删除会话 | `DELETE /auth/session/{id}` |
| `sendMessage(token, messages, mode)` | 普通聊天（支持 Agent 模式） | `POST /chatbot/chat` |
| `streamMessage(token, msgs, onChunk, onDone, mode, template)` | 流式聊天（支持 Agent 模式 + Workflow 模板） | `POST /chatbot/chat/stream` |
| `getMessages(token, mode)` | 获取历史消息（支持 legacy/v1/workflow 模式） | `GET /chatbot/messages` |
| `getWorkflowTemplates(token)` | 获取 Workflow 模板列表 | `GET /chatbot/workflow/templates` |
| `getPendingApprovals(token)` | 待审批列表 | `GET /approvals/pending` |
| `approveRequest(token, id, comment)` | 批准 | `POST /approvals/{id}/approve` |
| `rejectRequest(token, id, comment)` | 拒绝 | `POST /approvals/{id}/reject` |
| `validateToken(token)` | 验证 token 有效性（启动时调用） | `GET /auth/sessions` |
| `isNetworkError(err)` | 判断是否为网络连接错误（导出工具函数） | — |

**`buildChatUrl(mode, streaming)`** — 根据 Agent 模式和是否流式，自动构建正确的 API 路径：

| mode | streaming=false | streaming=true |
|------|----------------|----------------|
| `single` | `/chatbot/chat?mode=single` | `/chatbot/chat/stream?mode=single` |
| `multi` | `/chatbot/chat?mode=multi` | `/chatbot/chat/stream?mode=multi` |
| `workflow` | `/chatbot/workflow/chat` | `/chatbot/workflow/chat/stream` |

### 6.5 启动与开发

```bash
cd frontend
npm install       # 安装依赖
npm run dev       # 开发模式 http://localhost:3000
npm run build     # 生产构建 → dist/
npm run preview   # 预览生产构建
```

Vite 开发服务器会将 `/api` 开头的请求代理到 `http://localhost:8000`，无需配置 CORS。

### 6.6 自定义：添加新页面

1. 在 `frontend/src/pages/` 创建新组件
2. 在 `App.jsx` 添加路由：

```jsx
import MyPage from './pages/MyPage'

<Route path="/my-page" element={<MyPage auth={auth} onLogout={logout} />} />
```

3. 在需要的地方添加导航链接

---

## 7. 模块协作与完整调用链

### 7.1 Agent 模式调用链

各 Agent 模式的完整函数级调用链（精确到文件路径 + 函数名）已迁移至各模式的专属文档：

- **Single Agent**（Middleware 执行 + Agent 循环）→ [AGENT_MODE_2_V1_SINGLE.md § 函数调用链](./AGENT_MODE_2_V1_SINGLE.md#7-函数调用链)
- **V1 Multi-Agent**（Supervisor 路由 + Worker 执行 + HITL）→ [AGENT_MODE_3_V1_MULTI.md § 函数调用链](./AGENT_MODE_3_V1_MULTI.md#7-函数调用链)
- **Workflow**（Planner → Send 并行 → check → Synthesizer）→ [AGENT_MODE_4_WORKFLOW.md § 函数调用链](./AGENT_MODE_4_WORKFLOW.md#8-函数调用链)

---

#### 7.1.5 应用启动初始化调用链

```
app/main.py                              FastAPI app 启动
  │
  ├─ app/core/skills/registry.py         SkillRegistry.__init__()  [模块导入时]
  │     └─ _load_skills_from_prompts()
  │           └─ 遍历 app/core/skills/prompts/*.md
  │                 └─ _parse_skill_file(filepath) → Skill 对象
  │                       └─ [日志] "skill_loaded"  skill_name=sql_query / data_analysis / ...
  │
  ├─ app/services/llm.py                 LLMService.__init__()  [模块导入时]
  │     └─ LLMRegistry.__init_subclass__()
  │           └─ 注册 ChatOpenAI(model=Qwen3-14b, base_url=http://10.0.23.117:8180/v1)
  │
  ├─ app/api/v1/chatbot_v1.py           agent = V1Agent()  [模块导入时]
  │     ├─ V1Agent.__init__()
  │     │     ├─ self.llm_service = llm_service               全局 LLM 服务实例
  │     │     ├─ self._all_tools = list(tools)                 内置工具 (DuckDuckGo + load_skill)
  │     │     └─ llm_service.bind_tools(self._all_tools)       工具绑定到 LLM
  │     └─ (graph 在首次请求时懒创建)
  │
  └─ app/api/v1/api.py                  路由注册
        ├─ /chatbot/*     → chatbot_v1.router    (Single + Multi)
        ├─ /chatbot/workflow/* → chatbot_workflow.router (Workflow)
        └─ /approvals/*   → approval.router      (HITL)
```

---

#### 7.1.6 单 Agent 带 SkillCreator（创建 / 更新 Skill）

> 场景：用户发送 `"帮我创建一个 PostgreSQL 查询优化的技能"`，Agent 调用 `create_skill` 工具。

```
（前端 → API 层同 7.1.1，省略至 _graph.astream()）

  ▼ ── 第 1 轮 LangGraph 循环 ──

  app/core/langgraph/v1/agent.py          V1Agent (via Middleware)
    │
    ├─ SystemPromptMiddleware             Skills 描述已注入 system prompt（含 Available Skills 列表）
    ├─ prepare_messages()
    ├─ LLMService.call(messages)         LLM 返回 tool_calls: [create_skill]
    │
    ├─ [日志] "chat_node_routing_to_tools"   tool_names=['create_skill']
    └─ return Command(goto="tool_call")
         │
         ▼
  app/core/langgraph/v1/agent.py          V1Agent tool execution (via create_agent)
    │
    ├─ tool_call = state.messages[-1].tool_calls[0]
    │     name="create_skill", args={"instruction": "PostgreSQL 查询优化..."}
    │
    ├─ [日志] "tool_call_executing"          tool_name=create_skill
    │
    ├─ app/core/skills/registry.py       create_skill("PostgreSQL 查询优化...")
    │     │
    │     ├─ [日志] "create_skill_tool_invoked"  instruction_length=...
    │     │
    │     ├─ app/core/skills/creator.py  skill_creator.create_from_instruction(instruction, source="agent")
    │     │     ├─ [日志] "skill_creator_creating_from_instruction"
    │     │     ├─ LLM.ainvoke([SKILL_CREATE_SYSTEM_PROMPT, user_prompt])
    │     │     │     └─ LLM 返回 YAML frontmatter + Markdown 技能内容
    │     │     ├─ _parse_skill_response(response)  → Skill 对象
    │     │     ├─ [日志] "skill_creator_skill_created"  skill_name=postgresql_optimization
    │     │     └─ return Skill(name="postgresql_optimization", version=1, ...)
    │     │
    │     ├─ skill_registry.register_or_update(skill, persist=True)
    │     │     ├─ 新技能 → register + _save_skill_to_file()
    │     │     ├─ [日志] "skill_registered"  skill_name=postgresql_optimization
    │     │     └─ 写入 prompts/_auto/postgresql_optimization.md
    │     │
    │     └─ return "Skill 'postgresql_optimization' created successfully (v1)..."
    │
    ├─ [日志] "tool_call_completed"          tool_name=create_skill
    │
    └─ return Command(goto="chat")       ← 携带工具结果回到 chat 节点

  ▼ ── 第 2 轮 LangGraph 循环 ──

  app/core/langgraph/v1/agent.py          V1Agent (via Middleware)
    │
    ├─ messages 包含: [系统提示, 用户消息, AI tool_call, ToolMessage(创建成功)]
    ├─ LLMService.call(messages)         LLM 基于工具结果生成友好回复
    │
    └─ return Command(goto=END)
```

**日志输出时序**：
```
[info] chat_node_entered               model=...  user_input='帮我创建一个 PostgreSQL...'
[info] chat_node_routing_to_tools      tool_names=['create_skill']
[info] tool_call_executing             tool_name=create_skill
[info] create_skill_tool_invoked       instruction_length=...
[info] skill_creator_creating_from_instruction  instruction_length=...
[info] skill_creator_skill_created     skill_name=postgresql_optimization  source=agent
[info] skill_registered                skill_name=postgresql_optimization
[info] tool_call_completed             tool_name=create_skill
[info] chat_node_entered               ...     ← 第 2 轮
[info] chat_node_completed             response_length=...
```

> **update_skill 场景**与上述流程类似，区别在于 `_tool_call` 节点调用的是 `update_skill(skill_name, new_info)`，
> 内部由 `SkillCreator.update_skill()` 执行增量合并，`version` 自动递增。

---

#### 7.1.7 日志事件名 ↔ 函数 ↔ 文件 速查表

| 日志事件名 | 函数 | 文件 |
|-----------|------|------|
| `skill_loaded` | `SkillRegistry._load_skills_from_prompts()` | `app/core/skills/registry.py` |
| `skill_loaded_by_agent` | `load_skill()` | `app/core/skills/registry.py` |
| `skill_not_found` | `load_skill()` | `app/core/skills/registry.py` |
| `skill_registered` | `SkillRegistry.register()` | `app/core/skills/registry.py` |
| `create_skill_tool_invoked` | `create_skill()` | `app/core/skills/registry.py` |
| `update_skill_tool_invoked` | `update_skill()` | `app/core/skills/registry.py` |
| `skill_creator_creating_from_instruction` | `SkillCreator.create_from_instruction()` | `app/core/skills/creator.py` |
| `skill_creator_creating_from_conversation` | `SkillCreator.create_from_conversation()` | `app/core/skills/creator.py` |
| `skill_creator_skill_created` | `SkillCreator.create_from_instruction()` | `app/core/skills/creator.py` |
| `skill_creator_skill_extracted` | `SkillCreator.create_from_conversation()` | `app/core/skills/creator.py` |
| `skill_creator_skill_updated` | `SkillCreator.update_skill()` | `app/core/skills/creator.py` |
| `skill_creator_no_skill_in_conversation` | `SkillCreator.create_from_conversation()` | `app/core/skills/creator.py` |
| `skill_creator_creation_failed` | `SkillCreator.create_from_instruction()` | `app/core/skills/creator.py` |
| `skill_creator_update_failed` | `SkillCreator.update_skill()` | `app/core/skills/creator.py` |
| `mcp_tools_integrated` | `BaseAgentMixin._initialize_mcp_tools()` | `app/core/langgraph/base.py` |
| `v1_chat_request_received` | `chat_v1()` | `app/api/v1/chatbot_v1.py` |
| `v1_stream_request_received` | `chat_stream_v1()` | `app/api/v1/chatbot_v1.py` |
| `v1_multi_agent_initialized` | `V1MultiAgent.__init__()` | `app/core/langgraph/v1/multi_agent.py` |
| `tool_requires_hitl_approval` | `MultiAgentGraph._tool_call_node()` | `app/core/langgraph/multi_agent_graph.py` |
| `approval_request_created` | `ApprovalManager.create_request()` | `app/core/langgraph/hitl/manager.py` |
| `approval_request_approved` | `ApprovalManager.approve()` | `app/core/langgraph/hitl/manager.py` |
| `approval_request_rejected` | `ApprovalManager.reject()` | `app/core/langgraph/hitl/manager.py` |
| `connection_pool_created` | `BaseAgentMixin._get_connection_pool()` | `app/core/langgraph/base.py` |

### 7.2 完整请求生命周期

以下展示一个用户请求从前端发出到最终响应的完整调用链，涵盖所有新增模块的协作：

```
[前端 ChatPage]
  │
  ├─ 用户输入: "帮我删除数据库中 ID=5 的记录"
  │
  ▼
[API 层: chatbot.py]
  │
  ├─ JWT 验证 → get_current_session
  ├─ 速率限制检查
  │
  ▼
[MultiAgentGraph.get_response()]
  │
  ├─ 1. 检索长期记忆 → _get_relevant_memory(user_id, query)
  │
  ├─ 2. 调用 graph.ainvoke()
  │     │
  │     ▼
  │   [supervisor 节点]
  │     ├─ SupervisorAgent.route(messages)
  │     ├─ LLM 分析: 这是数据库操作 → worker="coder"
  │     ├─ 输出: RoutingDecision(worker="coder", reasoning="...")
  │     └─ Command(goto="worker")
  │     │
  │     ▼
  │   [worker 节点]
  │     ├─ WORKER_REGISTRY["coder"].invoke(messages)
  │     ├─ CoderWorker system prompt + 用户消息 → LLM
  │     ├─ LLM 返回: "需要调用 execute_sql 工具"
  │     ├─ response.tool_calls = [{"name": "execute_sql", ...}]
  │     └─ Command(goto="tool_call")
  │     │
  │     ▼
  │   [tool_call 节点]
  │     ├─ _requires_approval("execute_sql", args)
  │     ├─ "execute_sql" 匹配敏感模式 → True
  │     └─ Command(goto="approval_check")
  │     │
  │     ▼
  │   [approval_check 节点]
  │     ├─ approval_manager.create_request(
  │     │     session_id, "tool_execution",
  │     │     "Agent wants to execute: execute_sql"
  │     │   )
  │     ├─ 返回: ApprovalRequest(id="abc-123")
  │     ├─ 消息: "🔒 Approval required (ID: abc-123)"
  │     └─ Command(goto=END)  ← 暂停执行
  │
  ├─ 3. 响应返回前端: 显示审批等待消息
  │
  ▼
[前端 ApprovalsPage]
  │
  ├─ 轮询 GET /approvals/pending → 显示待审批项
  ├─ 审核人查看操作详情
  ├─ 点击 "Approve" + 评论
  │
  ▼
[API 层: approval.py]
  │
  ├─ POST /approvals/abc-123/approve
  ├─ approval_manager.approve("abc-123", comment="已确认")
  ├─ ApprovalRequest.status → APPROVED
  └─ asyncio.Event.set() → 唤醒等待协程（如有）
```

### 7.3 模块间依赖关系

```
                    ┌─────────────┐
                    │   config.py │ ← 全局配置（速率限制、模型、数据库等）
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ llm.py   │ │logging.py│ │metrics.py│
        │ (LLM服务)│ │ (日志)   │ │ (指标)   │
        └────┬─────┘ └──────────┘ └──────────┘
             │
    ┌────────┼──────────────────┐
    ▼        ▼                  ▼
┌────────┐ ┌────────────┐ ┌──────────┐
│ Skills │ │ Supervisor │ │  Workers │
│Registry│ │   Agent    │ │ (3 种)   │
└───┬────┘ └─────┬──────┘ └────┬─────┘
    │            │              │
    │            └──────┬───────┘
    ▼                   ▼
┌────────┐    ┌──────────────────┐
│ MCP    │    │ MultiAgentGraph  │ ← 编排所有模块
│Manager │───→│  + HITL Manager  │
└────────┘    └────────┬─────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   API 层         │
              │  chatbot.py     │
              │  approval.py    │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │    前端 React    │
              └─────────────────┘
```

---

## 8. 安全设计

### 8.1 认证与授权

| 层级 | 机制 | 实现 |
|------|------|------|
| 用户认证 | JWT Token | `app/utils/auth.py` |
| 会话隔离 | Session Token | `get_current_session` 依赖注入 |
| 审批权限 | Session 归属校验 | `approval_req.session_id != session.id → 403` |
| 输入清洗 | XSS 防护 | `app/utils/sanitization.py` |
| 密码安全 | 强度验证 | `validate_password_strength()` |

### 8.2 速率限制

| 端点组 | 限速 | 说明 |
|--------|------|------|
| 审批列表 | 50/min | 轮询场景 |
| 审批操作 | 20/min | 防止误操作 |
| 聊天 | 30/min | 普通聊天 |
| 流式聊天 | 20/min | SSE 长连接 |

### 8.3 HITL 安全屏障

- **默认拒绝原则**：敏感工具调用必须人工批准才能执行
- **超时过期**：未处理的审批请求 1 小时后自动过期
- **不可逆状态**：已批准/拒绝/过期的请求不可再次操作
- **审计日志**：所有审批操作通过 structlog 记录

---

## 9. 可观测性与日志

### 9.1 结构化日志事件

所有新增模块遵循项目的 structlog 日志规范，事件名使用 `lowercase_with_underscores` 格式：

| 事件名 | 模块 | 级别 | 说明 |
|--------|------|------|------|
| `skill_loaded` | Skills | INFO | 技能文件加载成功 |
| `skill_loaded_by_agent` | Skills | INFO | Agent 通过工具加载技能 |
| `skill_not_found` | Skills | WARN | 请求的技能不存在 |
| `skill_registered` | Skills | INFO | 技能注册成功（含自动生成） |
| `create_skill_tool_invoked` | SkillCreator | INFO | Agent 调用 create_skill 工具 |
| `update_skill_tool_invoked` | SkillCreator | INFO | Agent 调用 update_skill 工具 |
| `skill_creator_creating_from_instruction` | SkillCreator | INFO | 开始从指令创建技能 |
| `skill_creator_creating_from_conversation` | SkillCreator | INFO | 开始从对话提取技能 |
| `skill_creator_skill_created` | SkillCreator | INFO | 技能创建成功 |
| `skill_creator_skill_extracted` | SkillCreator | INFO | 从对话中提取技能成功 |
| `skill_creator_skill_updated` | SkillCreator | INFO | 技能增量更新成功 |
| `skill_creator_no_skill_in_conversation` | SkillCreator | INFO | 对话中未发现可提取的技能 |
| `skill_creator_creation_failed` | SkillCreator | ERROR | 技能创建失败 |
| `skill_creator_update_failed` | SkillCreator | ERROR | 技能更新失败 |
| `skill_saved_to_file` | Skills | INFO | 技能持久化到 _auto/ 目录 |
| `skill_unregistered` | Skills | INFO | 技能注销（含文件删除） |
| `mcp_server_connected` | MCP | INFO | MCP 服务器连接成功 |
| `mcp_tools_integrated` | MCP | INFO | MCP 工具集成到 Agent |
| `mcp_server_connection_failed` | MCP | ERROR | MCP 连接失败 |
| `supervisor_routing_decision` | Multi-Agent | INFO | Supervisor 路由决策 |
| `worker_response_generated` | Multi-Agent | INFO | Worker 生成响应 |
| `worker_execution_failed` | Multi-Agent | ERROR | Worker 执行失败 |
| `multi_agent_graph_created` | Multi-Agent | INFO | Graph 创建成功 |
| `approval_request_created` | HITL | INFO | 创建审批请求 |
| `approval_request_approved` | HITL | INFO | 审批请求被批准 |
| `approval_request_rejected` | HITL | INFO | 审批请求被拒绝 |
| `approval_request_expired` | HITL | WARN | 审批请求超时 |
| `approval_request_approved_via_api` | HITL API | INFO | 通过 API 批准 |

### 9.2 Prometheus 指标

- `llm_inference_duration_seconds`：LLM 推理耗时（含 Multi-Agent 中的 chat 节点）
- 所有 API 端点通过 `MetricsMiddleware` 自动采集请求计数和延迟

### 9.3 Langfuse 追踪

所有 Agent 模式均通过 `config["callbacks"]` 注入 `LangfuseCallbackHandler()` 实现追踪：

| Agent 模式 | 追踪注入位置 | 说明 |
|-----------|-------------|------|
| Single (`V1Agent`) | `get_stream_response()` | config callbacks 通过 `agent.astream()` 传播 |
| V1 Multi (`V1MultiAgent`) | `get_stream_response()` | config 通过 `supervisor_node(state, config)` 和 `worker_node(state, config)` 显式转发给子图的 `ainvoke(state, config=config)` |
| Workflow (`WorkflowGraph`) | `get_response()` / `get_stream_response()` | config callbacks 直接传播 |

V1 Multi Agent 的 `LangfuseTracingMiddleware` 仅做日志记录（logging-only），不再注入 callbacks，避免与 LangGraph 内部 callback 机制冲突。实际追踪由 config 层的 `LangfuseCallbackHandler()` 完成，并通过 `metadata` 中的 `langfuse_user_id` / `langfuse_session_id` 关联用户和会话。

---

## 10. 测试指南

### 10.1 已有测试

```
tests/
├── conftest.py                              # 共享 fixture
├── test_skills/
│   ├── test_schema.py                       # Skill 模型测试
│   └── test_registry.py                     # SkillRegistry 测试
├── test_mcp/
│   └── test_client.py                       # MCPManager 测试
└── test_integration/
    └── test_skills_mcp_integration.py       # Skills + MCP 集成测试
```

### 10.2 运行测试

```bash
# 所有测试
uv run pytest

# 仅 Skills 测试
uv run pytest tests/test_skills/ -v

# 仅 MCP 测试
uv run pytest tests/test_mcp/ -v

# 仅集成测试
uv run pytest tests/test_integration/ -v
```

### 10.3 建议补充的测试

| 测试目标 | 覆盖内容 |
|----------|----------|
| `SupervisorAgent.route()` | JSON 解析、容错回退、Worker 路由正确性 |
| `BaseWorker.invoke()` | 消息格式转换、LLM 调用、错误处理 |
| `ApprovalManager` | 创建/批准/拒绝/过期全流程 |
| `approval.py` API | 端点授权、会话隔离、状态码 |
| `MultiAgentGraph` | 端到端工作流、节点跳转 |
| 前端组件 | 登录流程、消息发送、审批操作 |

---

## 11. 部署注意事项

### 11.1 后端

```bash
# 安装依赖
uv sync

# 启动后端
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 11.2 前端

```bash
cd frontend
npm install
npm run build   # 生成 dist/ 目录
```

生产部署可将 `dist/` 托管在 Nginx/CDN，配置反向代理：

```nginx
location /api/ {
    proxy_pass http://backend:8000;
}
location / {
    root /path/to/frontend/dist;
    try_files $uri $uri/ /index.html;
}
```

### 11.3 环境变量

确保 `.env` 中配置了以下关键项：

| 变量 | 用途 |
|------|------|
| `OPENAI_API_KEY` | LLM API 密钥 |
| `DEFAULT_LLM_MODEL` | 默认模型名 |
| `POSTGRES_*` | 数据库连接 |
| `JWT_SECRET_KEY` | JWT 签名密钥 |
| `QDRANT_HOST` | Qdrant 服务地址（默认 `qdrant`） |
| `QDRANT_PORT` | Qdrant REST 端口（默认 `6333`） |
| `QDRANT_API_KEY` | Qdrant API 密钥（可选） |

### 11.4 MCP 服务器

如需使用 MCP 集成，确保 `mcp_servers.json` 中配置的外部服务可达。stdio 类型的服务器需要对应的 CLI 工具已安装。

---

## 12. 常见问题 FAQ

### Q: Multi-Agent 和单 Agent 有什么区别？应该用哪个？

**单 Agent** (`V1Agent`)：所有请求由一个通用 Agent 处理，适合简单场景。
**多 Agent** (`V1MultiAgent`)：Supervisor 自动路由到专业 Worker，适合需要领域专长的复杂场景。多 Agent 额外增加一次 LLM 调用（Supervisor 路由），但获得更精准的专业响应。

### Q: HITL 审批会不会阻塞其他用户的请求？

不会。每个审批请求有独立的 `asyncio.Event`，阻塞仅发生在对应的协程上下文中。其他用户的请求由独立的协程处理，互不影响。当前实现中 `approval_check` 节点是 goto END 然后返回消息，不会真正阻塞服务器。

### Q: 如何让某个 Worker 拥有独有的工具？

在创建 Worker 时传入工具列表：

```python
from my_tools import special_tool

WORKER_REGISTRY["my_worker"] = MyWorker(tools=[special_tool])
```

Worker 的 `invoke()` 方法会自动 `bind_tools` 然后调用 LLM。

### Q: 前端如何切换到生产 API 地址？

修改 `frontend/vite.config.js` 中 proxy 的 `target`，或在 `frontend/src/api.js` 中将 `API_BASE` 改为完整 URL：

```javascript
const API_BASE = 'https://api.example.com/api/v1'
```

### Q: 前端如何切换不同的 Agent 模式？

前端 ChatPage 顶部栏集成了 **Agent 模式选择器**，支持在以下 4 种模式之间一键切换：

| 模式 | 对应后端 API | 说明 |
|------|-------------|------|
| Single Agent | `/api/v1/chatbot/chat/stream?mode=single` | create_agent + Middleware |
| Multi Agent | `/api/v1/chatbot/chat/stream?mode=multi` | Supervisor + Worker 多智能体 |
| Workflow | `/api/v1/chatbot/workflow/chat/stream` | Orchestrator-Worker 多步工作流 |

- 选择 **Workflow** 模式后，会额外显示模板下拉框，可选择预定义的 Workflow 模板或使用 LLM 自动规划
- 模式选择持久化在 `localStorage` 中，刷新页面后保持
- 每种模式有独立的图标和颜色标识，方便区分当前使用的 Agent 类型
- `api.js` 中的 `buildChatUrl()` 函数根据模式自动构建正确的 API 路径

### Q: 如何添加新的敏感操作关键词？

修改 `MultiAgentGraph._requires_approval()` 中的 `sensitive_patterns` 列表。参见 [5.7 自定义：修改审批规则](#57-自定义修改审批规则)。

### Q: Skills 系统支持动态热加载吗？

当前实现在应用启动时一次性加载。如需热加载，可调用 `skill_registry._load_skills_from_prompts()` 重新扫描目录，或通过 `skill_registry.register()` 动态添加。此外，通过 `create_skill` / `update_skill` 工具创建的技能会**立即注册到内存**并**持久化到 `_auto/` 目录**，无需重启。

### Q: SkillCreator 创建技能时使用的是哪个 LLM？

`SkillCreator` 使用 `LLMRegistry.get(settings.DEFAULT_LLM_MODEL)` 获取当前配置的默认模型。如果你希望使用更强的模型来生成技能（例如 GPT-4o 而非 GPT-4o-mini），可以临时修改 `DEFAULT_LLM_MODEL` 环境变量，或修改 `creator.py` 中的 `_get_llm()` 方法指定特定模型。

### Q: 如何在对话中让 Agent 自动创建技能？

在对话中使用自然语言提示 Agent，例如：
- "帮我创建一个关于 Docker 部署最佳实践的技能"
- "把我们刚才讨论的 SQL 优化方法保存为一个技能"
- "学会这个模式，以后遇到类似问题就用它"

Agent 会识别意图并调用 `create_skill` 工具。如果你想从已有对话中提取知识，需要编程调用 `skill_creator.create_from_conversation(messages)`。

### Q: 自动生成的技能和手动创建的技能有什么区别？

| 维度 | 手动技能 | 自动生成技能 |
|------|---------|------------|
| 存储位置 | `prompts/*.md` | `prompts/_auto/*.md` |
| `auto_generated` | `false` | `true` |
| `source` | `manual` | `agent` 或 `conversation` |
| `version` | 默认 `1` | 自动递增 |
| 管理方式 | Git 版本控制 | `create_skill` / `update_skill` / `unregister` |

### Q: SkillCreator 失败了怎么办？

`create_skill` 和 `update_skill` 工具内部有完整的 `try/except` 错误处理。如果 LLM 调用失败或返回格式不正确，工具会返回友好的错误信息给 Agent，Agent 会通知用户重试或提供更具体的描述。查看日志中的 `skill_creator_creation_failed` 或 `skill_creator_update_failed` 事件可获取详细错误信息。

### Q: MCP 连接失败会影响 Agent 正常运行吗？

不会。`_initialize_mcp_tools()` 中对每个服务器的连接失败都做了异常捕获，失败的服务器会被跳过，Agent 仍然可以使用内置工具和 Skills 正常工作。

### Q: ApprovalManager 的数据是持久化的吗？

当前实现使用内存存储（`Dict[str, ApprovalRequest]`），适合开发和测试。生产环境建议替换为数据库存储，可以基于 `ApprovalRequest` 模型创建对应的 SQLModel 表。

### Q: RAG 知识库如何添加新的数据源？

编辑项目根目录的 `rag_providers.json`，在 `providers` 数组中添加新的 Provider 配置项（参见下方 Section 13.5「配置文件格式」）。如果需要对接新类型的数据源，实现 `BaseRetriever` 接口并注册到 `PROVIDER_REGISTRY`（参见下方 Section 13.9「自定义：添加新 Provider」）。

### Q: RAG 检索失败会影响 Agent 正常运行吗？

不会。`retrieve_knowledge` 工具内部有完整的异常捕获，单个 Provider 检索失败只会被跳过，其他 Provider 的结果仍会正常返回。如果所有 Provider 都失败，工具会返回 "No results found" 消息，Agent 可以继续用自身知识回答。

### Q: Qdrant Docker 镜像为什么用 wget 做健康检查？

Qdrant 官方 Docker 镜像**不包含 `curl`**，只有 `wget`。如果使用 `curl` 做 healthcheck 会导致容器一直处于 unhealthy 状态。

### Q: 后端重启后前端会怎样？

前端会自动检测连接中断并显示黄色 banner 提示用户。ChatPage 每 5 秒自动重试，ApprovalsPage 每 10 秒轮询。后端恢复后 banner 自动消失，无需用户手动刷新页面。详见 [Section 14](#14-前端连接恢复机制)。

### Q: 前端启动时 token 过期了怎么办？

`App.jsx` 在挂载时会调用 `validateToken()` 验证 localStorage 中的 token。如果后端返回非 200 状态或网络不可达，token 被判定为无效，用户自动跳转到登录页。验证期间会显示 loading spinner。

---

## 13. RAG 知识库集成

### 13.1 功能概述

**RAG（Retrieval-Augmented Generation）** 知识库集成实现了可插拔的多源检索架构，允许 Agent 从多种外部知识库中检索信息并增强回答质量。

核心设计：

- **可插拔 Provider 架构**：通过 `BaseRetriever` 抽象接口，统一不同数据源的检索行为
- **并行多源检索**：`RetrieverManager` 同时查询所有已启用的 Provider，合并去重结果
- **JSON 驱动配置**：通过 `rag_providers.json` 配置文件管理 Provider，无需修改代码
- **Agent 工具集成**：`retrieve_knowledge` 工具让 Agent 在对话中按需检索知识

### 13.2 支持的 Provider

| Provider | 类型标识 | 后端 | 适用场景 |
|----------|---------|------|---------|
| `QdrantRetriever` | `qdrant` | Qdrant 向量数据库 | 本地/自托管向量检索 |
| `PgvectorRetriever` | `pgvector` | PostgreSQL pgvector 扩展 | 共享 PostgreSQL 的向量检索 |
| `RAGFlowRetriever` | `ragflow` | RAGFlow（数据集检索 + OpenAI 兼容聊天） | 企业级 RAG 平台 |
| `GenericHTTPRetriever` | `http` | 任意 REST API（Dify / FastGPT / 自定义） | 对接已有知识库 API |

### 13.3 文件结构

```text
app/core/rag/
├── __init__.py                   # 模块导出
├── schema.py                     # RAGDocument, RetrievalQuery, RetrievalResult
├── base.py                       # BaseRetriever 抽象基类
├── manager.py                    # RetrieverManager（注册 + 并行检索 + 合并去重）
└── providers/
    ├── __init__.py               # PROVIDER_REGISTRY 类型映射
    ├── qdrant.py                 # QdrantRetriever
    ├── pgvector.py               # PgvectorRetriever
    ├── ragflow.py                # RAGFlowRetriever
    └── http.py                   # GenericHTTPRetriever

app/core/langgraph/tools/
└── rag_retrieve.py               # retrieve_knowledge Agent 工具

rag_providers.json                # Provider 配置文件（项目根目录）
```

### 13.4 核心类与接口

#### `BaseRetriever` — 抽象基类

```text
文件: app/core/rag/base.py
```

| 方法 | 签名 | 说明 |
|------|------|------|
| `initialize` | `async () -> None` | 初始化连接（如建立客户端、连接池） |
| `retrieve` | `async (query: RetrievalQuery) -> list[RAGDocument]` | 执行检索，返回文档列表 |
| `health_check` | `async () -> bool` | 健康检查 |
| `close` | `async () -> None` | 关闭连接 |

#### `RetrieverManager` — 检索管理器

```text
文件: app/core/rag/manager.py
```

| 方法 | 说明 |
|------|------|
| `register(name, retriever)` | 注册 Provider 实例 |
| `initialize_all()` | 异步初始化所有已注册 Provider |
| `retrieve(query)` | 并行查询所有 Provider，合并去重结果 |
| `close_all()` | 关闭所有 Provider 连接 |
| `load_providers_from_config()` | 从 `rag_providers.json` 加载并注册 Provider |

#### `PROVIDER_REGISTRY` — 类型映射

```python
# app/core/rag/providers/__init__.py
PROVIDER_REGISTRY = {
    "qdrant": QdrantRetriever,
    "pgvector": PgvectorRetriever,
    "ragflow": RAGFlowRetriever,
    "http": GenericHTTPRetriever,
}
```

#### 数据模型

```text
文件: app/core/rag/schema.py
```

| 类 | 说明 |
|----|------|
| `RAGDocument` | 检索结果文档（`content`、`metadata`、`score`、`source`） |
| `RetrievalQuery` | 检索请求（`query`、`top_k`、`filters`） |
| `RetrievalResult` | 检索响应（`documents`、`query`、`total_count`、`has_results`） |

### 13.5 配置文件格式

`rag_providers.json` 位于项目根目录，Docker 容器中挂载到 `/app/rag_providers.json`：

```json
{
  "providers": [
    {
      "name": "local-qdrant",
      "type": "qdrant",
      "enabled": true,
      "config": {
        "url": "http://qdrant:6333",
        "collection_name": "knowledge_base",
        "api_key": null
      }
    },
    {
      "name": "pg-knowledge",
      "type": "pgvector",
      "enabled": false,
      "config": {
        "connection_string": "postgresql://user:pass@db:5432/appdb",
        "collection_name": "documents"
      }
    },
    {
      "name": "ragflow-prod",
      "type": "ragflow",
      "enabled": false,
      "config": {
        "base_url": "http://ragflow:9380",
        "api_key": "ragflow-xxx",
        "dataset_ids": ["ds_001"],
        "mode": "retrieval"
      }
    },
    {
      "name": "dify-kb",
      "type": "http",
      "enabled": false,
      "config": {
        "base_url": "https://api.dify.ai/v1",
        "api_key": "app-xxx",
        "endpoint": "/datasets/{dataset_id}/retrieve",
        "method": "POST",
        "headers": {},
        "body_template": {"query": "{query}", "top_k": "{top_k}"},
        "response_content_path": "records[*].segment.content",
        "response_score_path": "records[*].score"
      }
    }
  ]
}
```

**Provider 字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | Provider 唯一名称 |
| `type` | `str` | 类型标识，对应 `PROVIDER_REGISTRY` 中的 key |
| `enabled` | `bool` | 是否启用 |
| `config` | `dict` | Provider 特定配置（传递给构造函数） |

### 13.6 调用链

```text
Agent 对话中 → LLM 决定需要检索知识
  │
  ▼
app/core/langgraph/tools/rag_retrieve.py    retrieve_knowledge(query, top_k=5)
  │
  ├─ RetrieverManager.load_providers_from_config()     首次调用时加载配置
  │     └─ 读取 rag_providers.json
  │     └─ 对每个 enabled=true 的 provider:
  │           └─ PROVIDER_REGISTRY[type](**config) → BaseRetriever 实例
  │           └─ manager.register(name, retriever)
  │
  ├─ RetrieverManager.initialize_all()                 异步初始化所有 Provider
  │     └─ asyncio.gather(*[r.initialize() for r in retrievers])
  │
  ├─ RetrieverManager.retrieve(RetrievalQuery(query, top_k))
  │     └─ asyncio.gather(*[r.retrieve(query) for r in retrievers])  并行检索
  │     └─ 合并 + 按 score 降序排序 + 取 top_k
  │
  └─ 格式化结果 → 返回给 Agent
        └─ "Source: local-qdrant\n内容: ...\n---\nSource: ragflow-prod\n内容: ..."
```

### 13.7 Docker 部署

`docker-compose-base.yml` 中包含 Qdrant 服务：

```yaml
qdrant:
  image: qdrant/qdrant:latest
  ports:
    - "6333:6333"    # REST API
    - "6334:6334"    # gRPC API
  volumes:
    - qdrant-data:/qdrant/storage
  healthcheck:
    test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:6333/healthz || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 5
```

> **注意**：Qdrant 官方 Docker 镜像**不包含 `curl`**，healthcheck 必须使用 `wget`。

`rag_providers.json` 挂载到 app 容器：

```yaml
app:
  volumes:
    - ./rag_providers.json:/app/rag_providers.json:ro
```

### 13.8 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `QDRANT_HOST` | `qdrant` | Qdrant 服务地址 |
| `QDRANT_PORT` | `6333` | Qdrant REST 端口 |
| `QDRANT_API_KEY` | — | Qdrant API 密钥（可选） |
| `QDRANT_COLLECTION_NAME` | `knowledge_base` | 默认集合名 |

### 13.9 自定义：添加新 Provider

**步骤 1**：在 `app/core/rag/providers/` 创建新文件

```python
# app/core/rag/providers/my_provider.py
from app.core.rag.base import BaseRetriever
from app.core.rag.schema import RAGDocument, RetrievalQuery

class MyProviderRetriever(BaseRetriever):
    """自定义 Provider。"""

    def __init__(self, api_url: str, api_key: str, **kwargs):
        super().__init__(name="my_provider", provider_type="my_type")
        self.api_url = api_url
        self.api_key = api_key

    async def initialize(self) -> None:
        # 初始化连接
        pass

    async def retrieve(self, query: RetrievalQuery) -> list[RAGDocument]:
        # 执行检索
        return [RAGDocument(content="...", metadata={}, score=0.9, source=self.name)]

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        pass
```

**步骤 2**：注册到 `PROVIDER_REGISTRY`

```python
# app/core/rag/providers/__init__.py
from .my_provider import MyProviderRetriever

PROVIDER_REGISTRY = {
    ...
    "my_type": MyProviderRetriever,
}
```

**步骤 3**：在 `rag_providers.json` 中添加配置

```json
{
  "name": "my-kb",
  "type": "my_type",
  "enabled": true,
  "config": {
    "api_url": "https://my-api.example.com",
    "api_key": "xxx"
  }
}
```

### 13.10 依赖

```toml
# pyproject.toml
"qdrant-client>=1.7.0"
"httpx>=0.27.0"
"langchain-postgres>=0.0.6"
"asyncpg>=0.29.0"
```

---

## 14. 前端连接恢复机制

### 14.1 问题背景

后端重启期间，前端会遇到以下问题：

- `fetch()` 抛出 `TypeError: Failed to fetch`（`ERR_CONNECTION_REFUSED`），但未被正确捕获
- 多个并发 API 调用同时收到 401，触发多次 `setAuth(null)` 导致页面闪烁
- localStorage 中的过期 token 未被验证，用户看到"已登录"但所有操作失败
- `streamMessage` 中 `onDone` 被调用两次（`data.done` + 循环结束后）
- 所有 `catch { }` 静默吞掉错误，用户看不到任何反馈
- 无连接恢复/重试机制

### 14.2 修复方案

#### `safeFetch` — 网络错误包装

所有 `fetch()` 调用替换为 `safeFetch()`，将网络层异常转为清晰的错误消息：

```javascript
async function safeFetch(url, options) {
  try {
    return await fetch(url, options)
  } catch (err) {
    throw new Error('Server is unreachable. Please check if the backend is running.')
  }
}
```

#### `handleResponse` — 401 防抖

防止多个并发 API 调用同时触发 logout：

```javascript
let _authErrorPending = false

async function handleResponse(res) {
  if (res.status === 401) {
    if (!_authErrorPending) {
      _authErrorPending = true
      setTimeout(() => { _authErrorPending = false }, 1000)
      _onAuthError?.()
    }
    throw new Error('Session expired')
  }
  return res
}
```

#### `validateToken` — 启动时 Token 验证

`App.jsx` 在渲染前异步验证 localStorage 中的 token：

```javascript
useEffect(() => {
  if (!auth?.userToken) { setValidating(false); return }
  validateToken(auth.userToken).then((valid) => {
    if (!valid) setAuth(null)
    setValidating(false)
  })
}, [])
```

验证期间显示 loading spinner，无效 token 自动跳转登录页。

#### `isNetworkError` — 网络错误检测

```javascript
export function isNetworkError(err) {
  return err && (
    err.name === 'TypeError' ||
    err.message === 'Failed to fetch' ||
    err.message?.includes('NetworkError')
  )
}
```

#### `streamMessage` — 修复双重 `onDone`

添加 `streamDone` 标志，确保 `onDone` 只调用一次：

```javascript
let streamDone = false
// ... in SSE loop:
if (data.done) { streamDone = true; onDone?.() }
// ... after loop:
if (!streamDone) onDone?.()
```

### 14.3 连接恢复 UI

#### ChatPage — 黄色 Banner + 自动重试

当检测到后端不可达时：

1. 显示黄色 banner：`⚠ 无法连接到服务器，正在自动重试...` + 手动重试按钮
2. 每 5 秒自动调用 `loadInitialData()` 尝试重新连接
3. 连接恢复后自动清除 banner 并加载数据

```text
┌─────────────────────────────────────────────────────────┐
│ ⚠ 无法连接到服务器，正在自动重试...        [重试]       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                    正常聊天界面                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### ApprovalsPage — 连接错误 Banner

同样显示黄色 banner，已有的 10 秒轮询机制自动充当重试功能。

### 14.4 i18n 支持

| Key | 中文 | English |
|-----|------|---------|
| `chat.connectionError` | 无法连接到服务器，正在自动重试... | Cannot reach server. Retrying automatically... |
| `chat.retry` | 重试 | Retry |

### 14.5 新增导出函数

| 函数 | 文件 | 说明 |
|------|------|------|
| `isNetworkError(err)` | `api.js` | 判断是否为网络连接错误 |
| `validateToken(token)` | `api.js` | 验证 token 是否仍被后端接受 |
| `safeFetch(url, options)` | `api.js`（内部） | 将 `fetch` 网络异常转为清晰错误 |

---

## 15. 模型评估框架

### 15.1 功能概述

`evals/` 模块提供基于 **Langfuse** 追踪数据的自动化模型质量评估框架。它从 Langfuse 拉取最近 24 小时的对话 trace，使用 LLM 按多个维度自动打分，分数回传 Langfuse 并生成本地 JSON 报告。

### 15.2 架构

```text
Langfuse 存储的 trace（最近 24h）
        │
        ▼
   Evaluator.__fetch_traces()
        │  过滤已评分的 trace
        ▼
   遍历每条 trace × 5 个指标
        │
        ▼
   _run_metric_evaluation()
        │  调用 OpenAI API 打分（0-1）
        ├─→ _push_to_langfuse()  回传分数到 Langfuse
        └─→ update_success/failure_metrics()
        │
        ▼
   generate_report()  → evals/reports/evaluation_report_YYYYMMDD_HHMMSS.json
```

### 15.3 文件结构

| 文件 | 职责 |
|------|------|
| `main.py` | CLI 入口，支持交互/快速/无报告三种模式 |
| `evaluator.py` | `Evaluator` 核心类：拉取 trace、调用 LLM 打分、推送 Langfuse |
| `helpers.py` | 辅助函数：消息格式化、报告初始化、指标汇总、JSON 报告生成 |
| `schemas.py` | `ScoreSchema`（Pydantic）：`score: float` + `reasoning: str` |
| `metrics/__init__.py` | 自动扫描 `prompts/` 目录加载所有 `.md` 指标文件 |
| `metrics/prompts/*.md` | 评估指标 Prompt（每个文件 = 一个指标） |

### 15.4 内置评估指标

| 指标 | 文件 | 评估维度 |
|------|------|---------|
| Relevancy | `relevancy.md` | 回复是否切题、是否直接回答用户问题 |
| Helpfulness | `helpfulness.md` | 回复是否有帮助、是否提供实用信息 |
| Conciseness | `conciseness.md` | 回复是否简洁、是否避免冗余 |
| Hallucination | `hallucination.md` | 是否存在幻觉、是否编造事实 |
| Toxicity | `toxicity.md` | 是否含有害、攻击性或不当内容 |

每个指标 Prompt 指导 LLM 按 0-1 连续评分并给出一句话推理。

### 15.5 前置条件

1. **Langfuse 已配置**：`.env` 中设置 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_HOST`
2. **已有对话数据**：Agent 已产生 Langfuse trace
3. **评估 LLM 可用**：默认使用 `EVALUATION_LLM` 环境变量指定的模型

### 15.6 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EVALUATION_LLM` | `gpt-5` | 用于打分的 LLM 模型 |
| `EVALUATION_BASE_URL` | `https://api.openai.com/v1` | 评估 API 地址 |
| `EVALUATION_API_KEY` | 复用 `OPENAI_API_KEY` | 评估 API 密钥 |
| `EVALUATION_SLEEP_TIME` | `10` | 两条 trace 间隔秒数（避免限流） |

### 15.7 运行方式

```bash
# 交互模式（可调整配置）
make eval ENV=development

# 快速模式（使用默认配置直接运行）
make eval-quick ENV=development

# 不生成 JSON 报告
make eval-no-report ENV=development

# Windows 用户（无 make）
python -m evals.main --interactive
python -m evals.main --quick
python -m evals.main --no-report
```

### 15.8 评估流程详解

1. `Evaluator.__init__()` 初始化 OpenAI 客户端和 Langfuse 客户端
2. `__fetch_traces()` 获取最近 24 小时**未评分**的 trace（`traces_without_scores`）
3. 遍历每条 trace，对每个指标调用 `_run_metric_evaluation()`：
   - `get_input_output(trace)` 从 trace 提取输入消息和输出消息
   - `_call_openai()` 调用 LLM，使用 `response_format=ScoreSchema` 强制结构化输出
   - 最多重试 3 次，每次失败间隔 10 秒
4. 成功后 `_push_to_langfuse()` 将分数推回 Langfuse（可在 Langfuse UI 查看）
5. 全部完成后 `generate_report()` 输出 JSON 报告到 `evals/reports/`

### 15.9 添加自定义指标

在 `evals/metrics/prompts/` 目录下创建新 `.md` 文件：

```markdown
Evaluate the [维度] of the generation on a continuous scale from 0 to 1.

## Scoring Criteria
A generation can be considered [维度] (Score: 1) if it:
- [标准1]
- [标准2]

## Example

### Input
[示例输入]

### Output
[示例输出]

### Evaluation
**Score**: 0.X
**Reasoning**: [一句话推理]

## Instructions
Think step by step.
```

文件保存后自动加载，无需修改代码。

### 15.10 核心类

| 类/方法 | 说明 |
|---------|------|
| `Evaluator` | 评估核心类，管理整个评估生命周期 |
| `Evaluator.run(generate_report_file)` | 主执行函数，拉取 trace 并逐条评估 |
| `Evaluator._run_metric_evaluation(metric, input, output)` | 单条 trace × 单指标评估 |
| `Evaluator._call_openai(prompt, input, output)` | 调用 LLM 打分（结构化输出） |
| `Evaluator._push_to_langfuse(trace, score, metric)` | 分数推回 Langfuse |
| `ScoreSchema` | Pydantic 模型：`score: float (0-1)` + `reasoning: str` |

---

## 16. 数据库 ORM 模型

### 16.1 功能概述

`app/models/` 目录定义所有数据库表结构，基于 **SQLModel**（SQLAlchemy + Pydantic 融合框架）。这些模型被 `DatabaseService`（`app/services/database.py`）用于用户、会话和线程的 CRUD 操作。

### 16.2 模型一览

| 文件 | 模型类 | 数据库表 | 职责 |
|------|--------|---------|------|
| `base.py` | `BaseModel` | — | 基类，提供 `created_at: datetime` 公共字段 |
| `user.py` | `User` | `user` | 用户账号：email（唯一索引）+ bcrypt 哈希密码 |
| `session.py` | `Session` | `session` | 聊天会话：属于某 User，存储会话名称 |
| `thread.py` | `Thread` | `thread` | 对话线程：用于 LangGraph checkpoint 关联 |
| `database.py` | — | — | 模型导出入口（`__all__ = ["Thread"]`） |

### 16.3 模型关系

```text
User (1) ──→ (N) Session
  │                 │
  │ id (int, PK)    │ id (str, PK)
  │ email (unique)  │ user_id (FK → user.id)
  │ hashed_password │ name
  │ created_at      │ created_at
  │                 │
  └─ sessions ←─────┘ user (back_populates)

Thread
  │ id (str, PK)
  │ created_at
```

### 16.4 关键实现细节

#### User 模型

```python
class User(BaseModel, table=True):
    id: int = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    sessions: List["Session"] = Relationship(back_populates="user")

    def verify_password(self, password: str) -> bool:
        """使用 bcrypt 验证密码"""
        return bcrypt.checkpw(password.encode("utf-8"), self.hashed_password.encode("utf-8"))

    @staticmethod
    def hash_password(password: str) -> str:
        """使用 bcrypt 哈希密码"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
```

- **密码安全**：使用 `bcrypt` 加盐哈希，不存储明文
- **关系**：`sessions` 一对多关联到 `Session`
- **索引**：`email` 字段有唯一索引，加速查询

#### Session 模型

```python
class Session(BaseModel, table=True):
    id: str = Field(primary_key=True)         # UUID 字符串
    user_id: int = Field(foreign_key="user.id")
    name: str = Field(default="")
    user: "User" = Relationship(back_populates="sessions")
```

- **主键**：UUID 字符串（非自增整数）
- **外键**：`user_id` 关联到 `user.id`

#### Thread 模型

```python
class Thread(SQLModel, table=True):
    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

- 用于 LangGraph 的 checkpoint 持久化
- 独立于 User/Session 关系，由 LangGraph 内部管理

### 16.5 数据库表创建

表结构定义在项目根目录的 `schema.sql` 中：

```bash
# Docker Compose 首次启动时自动执行
# 本地开发需手动执行：
psql -U myuser -d mydb -f schema.sql
```

### 16.6 在服务层使用

模型通过 `DatabaseService`（`app/services/database.py`）提供 CRUD 接口：

| 方法 | 说明 |
|------|------|
| `create_user(email, password)` | 创建用户（自动哈希密码） |
| `get_user_by_email(email)` | 按 email 查询用户 |
| `create_session(user_id)` | 创建聊天会话 |
| `get_user_sessions(user_id)` | 获取用户的所有会话 |
| `delete_session(session_id)` | 删除会话 |
| `health_check()` | 数据库连接健康检查 |

---

## 17. Prometheus 指标采集

### 17.1 功能概述

`prometheus/` 目录配置 **Prometheus** 时序数据库，定时抓取后端应用和 cAdvisor 暴露的指标数据，供 Grafana 查询可视化。后端通过 `app/core/metrics.py` 定义和暴露指标。

### 17.2 架构

```text
FastAPI 后端 (app:8000)
    │
    ├─ /metrics 端点（starlette_prometheus 自动暴露）
    │   ├─ http_requests_total
    │   ├─ http_request_duration_seconds
    │   ├─ db_connections
    │   ├─ llm_inference_duration_seconds
    │   └─ llm_stream_duration_seconds
    │
    ▼
Prometheus (localhost:9090)
    │  每 15s 抓取一次
    │
    ├─ job: fastapi  → targets: ['app:8000']
    └─ job: cadvisor → targets: ['cadvisor:8080']
    │
    ▼
Grafana (localhost:3000)
    └─ 数据源: Prometheus → 仪表板可视化
```

### 17.3 配置文件

`prometheus/prometheus.yml`：

```yaml
global:
  scrape_interval: 15s       # 每 15 秒采集一次
  evaluation_interval: 15s   # 每 15 秒评估一次告警规则

scrape_configs:
  - job_name: 'fastapi'      # 抓取后端 /metrics 端点
    metrics_path: '/metrics'
    scheme: 'http'
    static_configs:
      - targets: ['app:8000']

  - job_name: 'cadvisor'     # 抓取 cAdvisor 容器指标
    static_configs:
      - targets: ['cadvisor:8080']
```

### 17.4 后端暴露的指标

定义在 `app/core/metrics.py` 中：

| 指标名 | 类型 | 标签 | 说明 |
|--------|------|------|------|
| `http_requests_total` | Counter | method, endpoint, status | HTTP 请求总数 |
| `http_request_duration_seconds` | Histogram | method, endpoint | HTTP 请求耗时分布 |
| `db_connections` | Gauge | — | 当前活跃数据库连接数 |
| `llm_inference_duration_seconds` | Histogram | model | LLM 非流式推理耗时（buckets: 0.1-5s） |
| `llm_stream_duration_seconds` | Histogram | model | LLM 流式推理耗时（buckets: 0.1-10s） |

### 17.5 指标注入方式

```python
# app/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge
from starlette_prometheus import metrics, PrometheusMiddleware

def setup_metrics(app):
    app.add_middleware(PrometheusMiddleware)  # 自动采集 HTTP 指标
    app.add_route("/metrics", metrics)        # 暴露 /metrics 端点
```

在 `app/main.py` 启动时调用 `setup_metrics(app)`。

LLM 推理耗时在 Agent 调用 LLM 时手动记录：

```python
from app.core.metrics import llm_inference_duration_seconds

with llm_inference_duration_seconds.labels(model="gpt-4o-mini").time():
    response = await llm.ainvoke(messages)
```

V1 Agent 的 `MetricsMiddleware` 自动完成此操作。

### 17.6 使用方式

1. Docker Compose 启动后，访问 **http://localhost:9090** 进入 Prometheus UI
2. 在查询框输入 PromQL 表达式：

```promql
# 每分钟 HTTP 请求速率
rate(http_requests_total[5m])

# LLM 推理 P95 延迟
histogram_quantile(0.95, rate(llm_inference_duration_seconds_bucket[1m]))

# LLM 流式推理平均耗时
rate(llm_stream_duration_seconds_sum[1m]) / rate(llm_stream_duration_seconds_count[1m])
```

3. 本地验证指标暴露：直接访问 **http://localhost:8000/metrics** 查看原始 Prometheus 格式输出

### 17.7 添加自定义指标

在 `app/core/metrics.py` 中定义新指标：

```python
from prometheus_client import Counter

my_custom_counter = Counter(
    "my_custom_total",
    "Description of my custom metric",
    ["label1", "label2"]
)
```

然后在业务代码中调用 `my_custom_counter.labels(label1="x", label2="y").inc()`。

---

## 18. Grafana 监控仪表板

### 18.1 功能概述

`grafana/dashboards/` 提供预配置的 **Grafana 监控仪表板**，通过 Docker Compose 启动时自动加载（provisioning），可视化展示 LLM 推理性能指标。

### 18.2 自动加载机制

`grafana/dashboards/dashboards.yml` 配置了 Grafana 的 **provisioning**：

```yaml
apiVersion: 1
providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /etc/grafana/provisioning/dashboards/json
```

Grafana 启动时自动扫描 `json/` 目录中的 JSON 文件并导入为仪表板。

### 18.3 内置仪表板：LLM Inference Latency

文件：`grafana/dashboards/json/llm_latency.json`

包含 **4 个面板**：

| 面板 | PromQL 查询 | 说明 |
|------|------------|------|
| LLM Inference Duration (p95) | `histogram_quantile(0.95, rate(llm_inference_duration_seconds_bucket[1m]))` | 非流式推理 P95 延迟，按模型分组 |
| LLM Stream Duration (p95) | `histogram_quantile(0.95, rate(llm_stream_duration_seconds_bucket[1m]))` | 流式推理 P95 延迟，按模型分组 |
| LLM Inference Duration (avg) | `rate(…_sum[1m]) / rate(…_count[1m])` | 非流式推理平均延迟 |
| LLM Inference Request Count | `rate(llm_inference_duration_seconds_count[1m])` | 每分钟推理请求数，按模型分组 |

仪表板自动刷新间隔：**10 秒**。

### 18.4 使用方式

1. 通过 Docker Compose 启动：
   ```bash
   docker compose up -d
   ```

2. 访问 Grafana：**http://localhost:3000**（默认账号 `admin`，密码 `admin`）

3. 左侧导航 → **Dashboards** → 找到 **"LLM Inference Latency"**

4. Prometheus 数据源已在 Docker Compose 中自动配置，无需手动添加

### 18.5 添加自定义仪表板

**方式 1：JSON 文件**

在 `grafana/dashboards/json/` 目录创建新的 `.json` 文件，格式：

```json
{
  "dashboard": {
    "id": null,
    "uid": "my-dashboard",
    "title": "My Custom Dashboard",
    "panels": [
      {
        "type": "graph",
        "title": "Panel Title",
        "targets": [
          {
            "expr": "your_promql_query",
            "legendFormat": "{{label}}",
            "refId": "A"
          }
        ],
        "datasource": "Prometheus",
        "gridPos": { "x": 0, "y": 0, "w": 24, "h": 9 }
      }
    ]
  },
  "overwrite": true
}
```

重启 Grafana 即自动加载。

**方式 2：UI 创建后导出**

1. 在 Grafana UI 手动创建仪表板
2. 仪表板设置 → JSON Model → 复制 JSON
3. 保存到 `grafana/dashboards/json/` 目录

### 18.6 四个模块协作关系

```text
用户与 Agent 对话
   │
   ├─→ app/models/     数据持久化（User/Session/Thread → PostgreSQL）
   │
   ├─→ Langfuse        记录 LLM trace（输入、输出、token、耗时）
   │     │
   │     └─→ evals/    拉取 trace → LLM 打分 → 回传 Langfuse + 本地 JSON 报告
   │
   ├─→ /metrics 端点   暴露 Prometheus 指标（HTTP、LLM、DB）
   │     │
   │     └─→ prometheus/    每 15s 抓取指标数据
   │           │
   │           └─→ grafana/dashboards/    可视化面板展示延迟、QPS 等
   │
   └─→ cAdvisor        容器级别指标（CPU、内存、网络）
         │
         └─→ prometheus/ → grafana/
```

---

> **文档版本**: 1.8
> **最后更新**: 2026-02-07
> **覆盖模块**: Skills · **SkillCreator** · MCP · Multi-Agent · HITL · Frontend（Markdown 渲染 · 会话侧栏 · 401 拦截 · 代码分割 · **连接恢复**） · V1 Middleware（LangChain v1.2.8 API 适配） · Langfuse 追踪（config 层 CallbackHandler） · Workflow 编排引擎 · **RAG 知识库**（Qdrant · pgvector · RAGFlow · HTTP） · **模型评估框架**（Langfuse trace + LLM 打分） · **数据库 ORM 模型**（SQLModel） · **Prometheus 指标采集** · **Grafana 监控仪表板**
