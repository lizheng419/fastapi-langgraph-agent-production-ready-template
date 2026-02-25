# 变更日志 (CHANGELOG)

本文档记录项目的功能迭代、Bug 修复和重要变更，按版本倒序排列。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范。

---

## [1.9.0] - 2026-02-24

### 新增 (Features)

- **RAG 文档导入管线**：前端上传 → PDF/TXT/MD/DOCX 解析 → 文本切块 → 向量化 → Qdrant 写入
  - 后端：`app/core/rag/ingest.py`（`parse_document`、`chunk_text`、`ingest_document`、`list_documents`、`delete_document`）
  - API：`app/api/v1/rag.py` — `POST /upload`、`GET /documents`、`DELETE /documents/{doc_id}`
  - 前端：`KnowledgePage.jsx`（拖拽上传、文档列表、删除、进度反馈）
  - 路由：`/knowledge`，侧边栏「知识库」入口
  - i18n：`knowledge.*` 命名空间（中/英 25 个 key）
- **新增依赖**：`pypdf>=5.0.0`、`python-docx>=1.1.0`、`langchain-text-splitters>=0.3.0`

### 变更 (Changes)

- `app/api/v1/api.py`：注册 RAG 路由 `prefix="/rag"`
- `frontend/src/api.js`：新增 `uploadDocument`、`getDocuments`、`deleteDocument` API 函数
- `frontend/src/App.jsx`：添加 `/knowledge` 路由
- `frontend/src/pages/ChatPage.jsx`：侧边栏新增「知识库」导航按钮

### 文档 (Docs)

- `PROJECT_DOCUMENTATION_CN.md`：项目树新增 `ingest.py`、`KnowledgePage.jsx`；API 端点新增 4.5 RAG 知识库端点
- `NEW_FEATURES_GUIDE.md`：新增第 19 章「RAG 文档导入与知识库管理」
- `QUICK_START.md`：新增 9.5 知识库管理章节
- `README.md`：RAG 功能描述新增文档导入管线；项目树新增 `ingest.py`、`KnowledgePage.jsx`
- `AGENTS.md`：新增 RAG Document Ingestion 子节；Key Dependencies 新增 3 个库

---

## [1.8.0] - 2026-02-07

### 新增 (Features)

- **Grafana 监控仪表板**：`grafana/dashboards/json/llm_latency.json` 预置 4 个面板（P95 延迟、流式 P95、平均延迟、请求频率）
  - Provisioning 自动加载：`grafana/provisioning/datasources/datasource.yml` + `grafana/dashboards/dashboards.yml`
  - 数据源 UID：`prometheus`（自动配置，无需手动添加）
- **Prometheus 指标采集**：`llm_inference_duration_seconds`、`llm_stream_duration_seconds` 直方图指标
- **cAdvisor 容器监控**：Docker 容器级 CPU/内存/网络指标

### Bug 修复 (Fixes)

- **Grafana 容器重启循环**：`datasource.yml` 缺少显式 `uid: prometheus`，导致仪表板无法关联数据源
- **Grafana 仪表板无数据**：PromQL `rate()` 窗口从 `[1m]` 调整为 `[5m]`，解决稀疏请求场景下无数据问题
- **Grafana Dashboard JSON 格式错误**：文件 provisioning 不应包裹 `{"dashboard": {...}, "overwrite": true}`；面板类型从已废弃的 `graph` 改为 `timeseries`

### 文档 (Docs)

- `NEW_FEATURES_GUIDE.md`：第 18 章 Grafana 监控仪表板（JSON 格式、PromQL 示例、自定义面板指南）
- `PROJECT_DOCUMENTATION_CN.md`：8.2 节新增 Grafana 仪表板和 datasource provisioning 说明

---

## [1.7.0] - 2026-02-06

### 新增 (Features)

- **RAG 知识库集成**：可插拔 Provider 架构
  - `BaseRetriever` 抽象接口 + `RetrieverManager`（并行检索、结果合并去重）
  - 4 个内置 Provider：`QdrantRetriever`、`PgvectorRetriever`、`RAGFlowRetriever`、`GenericHTTPRetriever`
  - JSON 配置：`rag_providers.json`（无需改代码即可添加新数据源）
  - Agent 工具：`retrieve_knowledge`（跨所有 Provider 搜索并合并结果）
- **Qdrant 向量数据库**：Docker Compose 集成（端口 6333/6334），healthcheck 使用 wget

### Bug 修复 (Fixes)

- **Embedding 维度不匹配**：`expected 1536 dimensions, not 768` — mem0 pgvector 未配置 `embedding_model_dims`
  - 新增 `LONG_TERM_MEMORY_EMBEDDER_DIMS` 环境变量（默认 1536）
  - `.env` / `.env.example` / `config.py` 同步更新

---

## [1.6.0] - 2026-02-05

### 新增 (Features)

- **V1 Middleware 异步支持**：所有 `AgentMiddleware` 子类实现 `awrap_model_call` / `awrap_tool_call`
  - `LangfuseTracingMiddleware`、`MetricsMiddleware`、`HITLApprovalMiddleware` 完整异步适配
  - 解决 `astream()` / `ainvoke()` 调用时 `NotImplementedError` 问题
- **SummarizationMiddleware**：内置对话摘要中间件，自动压缩过长对话历史
  - 配置：`SUMMARIZATION_MODEL`、`SUMMARIZATION_TRIGGER_TOKENS`(4000)、`SUMMARIZATION_KEEP_MESSAGES`(20)
- **`@dynamic_prompt skills_aware_prompt`**：替代原 `SystemPromptMiddleware`，遵循 LangChain Context Engineering 官方指南
- **`@wrap_model_call role_based_tool_filter`**：按用户角色动态过滤工具（admin 全部工具，普通用户不可访问 `create_skill`/`update_skill`）

### 变更 (Changes)

- `MemoryContext` → `AgentContext`（保留向后兼容别名），新增 `user_role` 字段
- 移除 `LongTermMemoryMiddleware`（记忆读取移入 `skills_aware_prompt`）

---

## [1.5.0] - 2026-02-04

### 新增 (Features)

- **Workflow 编排引擎**：基于 LangGraph Orchestrator-Worker + Send API
  - `WorkflowPlanner`（YAML 模板匹配 + LLM 动态规划）
  - `WorkflowGraph`（并行执行 + 依赖链调度）
  - 预置模板：`code_review.yaml`、`research_report.yaml`
- **前端 Workflow 模式**：Agent 模式选择器新增 Workflow 选项，支持选择模板

---

## [1.4.0] - 2026-02-03

### 新增 (Features)

- **HITL 人工审批系统**：敏感操作自动拦截 + 审批队列
  - `HITLApprovalMiddleware`：基于 pattern 匹配拦截敏感工具调用
  - REST API：`/api/v1/approvals/*`（pending/approve/reject）
  - 前端：`ApprovalsPage.jsx` 审批管理界面
- **前端连接恢复机制**：网络断开时自动重连 + 错误提示

---

## [1.3.0] - 2026-02-02

### 新增 (Features)

- **SkillCreator 自动创建技能**：LLM 驱动的技能自动生成 + 增量学习
  - Agent 工具：`create_skill`、`update_skill`、`list_all_skills`
  - 自动生成 Skill 持久化到 `app/core/skills/prompts/_auto/`
- **MCP 集成**：Model Context Protocol 外部工具发现
  - SSE + stdio 双传输支持
  - 配置：`mcp_servers.json`
  - 启动时自动发现并注册工具

---

## [1.2.0] - 2026-02-01

### 新增 (Features)

- **Skills 渐进式加载系统**：仅简短描述出现在系统提示词中，完整内容按需加载
  - `load_skill` 工具：Agent 按需加载技能详情
  - 预置技能：`api_design`、`code_review`、`data_analysis`、`sql_query`
- **V1 Multi-Agent**：Supervisor + Worker 多智能体协作
  - Worker 角色：`researcher`、`coder`、`analyst`

---

## [1.1.0] - 2026-01-31

### 新增 (Features)

- **V1 Single Agent**：基于 `create_agent` + Middleware 组合
  - Langfuse 追踪中间件
  - Prometheus 指标中间件
  - 长期记忆（mem0ai + PostgreSQL pgvector）
- **前端 React 应用**：聊天界面 + 会话侧栏 + Agent 模式选择 + i18n（中/英）
- **Markdown 渲染组件**：GFM + 代码高亮 + 一键复制

---

## [1.0.0] - 2026-01-30

### 新增 (Features)

- **项目初始化**：FastAPI + LangGraph + PostgreSQL 基础架构
- **JWT 认证**：注册/登录/Session 管理
- **LangGraph Checkpointing**：AsyncPostgresSaver 持久化
- **Langfuse 集成**：LLM 调用追踪
- **Docker Compose**：PostgreSQL + 后端 + 前端一键部署
- **SQLModel ORM**：User + Session 模型 + 数据库迁移脚本

---

> **维护说明**：每次功能迭代或 Bug 修复后，请在对应版本下添加条目。使用以下分类：
>
> - **新增 (Features)**：新功能
> - **变更 (Changes)**：对已有功能的修改
> - **Bug 修复 (Fixes)**：错误修复
> - **文档 (Docs)**：文档更新
> - **移除 (Removed)**：移除的功能
> - **安全 (Security)**：安全相关变更
