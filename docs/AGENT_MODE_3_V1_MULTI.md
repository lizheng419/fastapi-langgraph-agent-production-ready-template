# Agent 模式 3：V1 Multi-Agent（Supervisor + Workers）

> 本文档详细讲解 V1 Multi-Agent 模式的实现原理、Supervisor 路由机制、Worker 架构、函数调用链、使用方式和示例。

---

## 目录

1. [模式概述](#1-模式概述)
2. [架构图](#2-架构图)
3. [核心文件](#3-核心文件)
4. [Supervisor-Worker 模式详解](#4-supervisor-worker-模式详解)
5. [Worker 定义与注册](#5-worker-定义与注册)
6. [类与函数详解](#6-类与函数详解)
7. [函数调用链](#7-函数调用链)
8. [Graph 构建详解](#8-graph-构建详解)
9. [API 端点](#9-api-端点)
10. [使用示例](#10-使用示例)
11. [扩展：添加自定义 Worker](#11-扩展添加自定义-worker)

---

## 1. 模式概述

V1 Multi-Agent 基于 **Supervisor + Worker** 模式：一个 Supervisor Agent 分析用户请求并路由到最合适的专家 Worker Agent。每个 Worker 是独立的 `create_agent` 实例，拥有自己的系统提示词和 Middleware 栈。

| 属性 | 值 |
|------|------|
| **实现类** | `V1MultiAgent` |
| **源文件** | `app/core/langgraph/v1/multi_agent.py` |
| **API 前缀** | `/api/v1/chatbot?mode=multi` |
| **路由文件** | `app/api/v1/chatbot_v1.py` |
| **Graph 类型** | `StateGraph` + `create_agent` Workers |
| **关键特性** | LLM 智能路由、专家 Worker、Handoff Tools、独立 Middleware |

---

## 2. 架构图

```text
用户请求
   │
   ▼
FastAPI 路由 (chatbot_v1.py)
   │  POST /api/v1/chatbot/chat?mode=multi
   │
   ▼
V1MultiAgent.get_response()
   │
   ├─ _get_relevant_memory()            ← mem0 记忆检索
   ├─ 构建 memory system message        ← 将记忆作为 system 消息前置
   │
   ▼
CompiledStateGraph.ainvoke()
   │
   │  ┌──────────────────────────────────────────────┐
   │  │                                              │
   │  │  [supervisor] 节点                            │
   │  │    │  Supervisor create_agent 分析请求         │
   │  │    │  通过 handoff tool 路由                   │
   │  │    │                                          │
   │  │    ├─ transfer_to_researcher → [researcher]   │
   │  │    ├─ transfer_to_coder     → [coder]         │
   │  │    ├─ transfer_to_analyst   → [analyst]       │
   │  │    └─ 无 handoff（直接回复）  → END            │
   │  │                                              │
   │  │  [worker_name] 节点                           │
   │  │    │  Worker create_agent 独立处理             │
   │  │    │  （含 Middleware: 追踪/指标/HITL）         │
   │  │    └─ → END                                   │
   │  │                                              │
   │  └──────────────────────────────────────────────┘
   │
   ▼
_update_long_term_memory()              ← 后台更新记忆
   │
   ▼
返回响应给用户
```

---

## 3. 核心文件

| 文件路径 | 职责 |
|---------|------|
| `app/core/langgraph/v1/multi_agent.py` | `V1MultiAgent` 类：Graph 构建、Supervisor/Worker 创建 |
| `app/core/langgraph/v1/middleware.py` | Worker Middleware 栈（HITL、追踪、指标） |
| `app/api/v1/chatbot_v1.py` | 共享路由：`?mode=multi` 切换到多 Agent |
| `app/core/langgraph/v1/agent.py` | `V1Agent`（单 Agent，与 multi 共享路由入口） |
| `app/services/llm.py` | `LLMRegistry`：模型注册与获取 |

---

## 4. Supervisor-Worker 模式详解

### 4.1 设计理念

```text
                    ┌──────────────┐
     用户消息 ──→   │  Supervisor  │   ← LLM 分析请求类型
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │researcher│ │  coder   │ │ analyst  │
        └──────────┘ └──────────┘ └──────────┘
              │            │            │
              └────────────┼────────────┘
                           │
                           ▼
                        用户响应
```

- **Supervisor**：一个 `create_agent` 实例，配备 **handoff tools**（如 `transfer_to_researcher`）
- **Worker**：每个是独立 `create_agent` 实例，有专属系统提示词和 Middleware
- **路由机制**：Supervisor 调用 handoff tool → Graph 捕获 tool_call → `Command(goto=worker_name)`

### 4.2 Handoff Tool 机制

```python
# 为每个 Worker 动态创建 handoff tool
for worker_name in workers:
    @tool(f"transfer_to_{worker_name}")
    def _make_handoff(request: str, _name=worker_name) -> str:
        """Transfer the request to a specialist worker."""
        return f"Transferring to {_name}: {request}"

    _make_handoff.__doc__ = f"Transfer to {worker_name} specialist. ..."
    handoff_tools.append(_make_handoff)
```

Supervisor 的 LLM 看到这些工具描述后，根据用户请求内容决定调用哪个 `transfer_to_*` 工具。

### 4.3 路由判定流程

```text
Supervisor LLM 推理
   │
   ├─ 调用 transfer_to_researcher("查找 AI 论文")
   │   → supervisor_node 检测到 handoff tool_call
   │   → Command(goto="researcher")
   │
   ├─ 调用 transfer_to_coder("写一个排序算法")
   │   → Command(goto="coder")
   │
   └─ 不调用任何 handoff tool（直接回复）
       → Command(goto=END)
```

---

## 5. Worker 定义与注册

### 5.1 内置 Worker 配置

```python
# app/core/langgraph/v1/multi_agent.py

WORKER_CONFIGS: Dict[str, dict] = {
    "researcher": {
        "system_prompt": (
            "You are a research specialist. Your strengths:\n"
            "- Web search and information gathering\n"
            "- Fact-checking and source verification\n"
            "- Summarizing complex topics into clear reports\n"
            "- Finding relevant data and statistics\n\n"
            "Always cite sources when possible and present findings clearly."
        ),
        "description": "Research, web search, information gathering, fact-checking",
    },
    "coder": {
        "system_prompt": "You are a coding specialist...",
        "description": "Code writing, debugging, review, architecture",
    },
    "analyst": {
        "system_prompt": "You are a data analysis specialist...",
        "description": "Data analysis, statistics, SQL, visualization",
    },
}
```

### 5.2 Worker 能力矩阵

| Worker | 擅长领域 | 路由关键词示例 |
|--------|---------|--------------|
| **researcher** | 信息搜索、事实核查、报告撰写 | "查找"、"搜索"、"调研"、"论文" |
| **coder** | 代码编写、调试、架构设计 | "写代码"、"debug"、"实现"、"算法" |
| **analyst** | 数据分析、统计、SQL、可视化 | "分析数据"、"统计"、"SQL"、"图表" |

---

## 6. 类与函数详解

### 6.1 V1MultiAgentConfig

```python
@dataclass
class V1MultiAgentConfig:
    model: str = settings.DEFAULT_LLM_MODEL
    enable_hitl: bool = True           # Worker 级别 HITL
    enable_tracing: bool = True        # Worker 级别 Langfuse
    enable_metrics: bool = True        # Worker 级别 Prometheus
    enable_memory: bool = True         # 长期记忆
    sensitive_patterns: Optional[List[str]] = None
    worker_configs: Optional[Dict[str, dict]] = None  # 自定义 Worker
```

### 6.2 _build_worker_middleware()

```python
def _build_worker_middleware(self) -> list:
    """为 Worker Agent 构建 Middleware 栈。"""
    middlewares = []
    if self._config.enable_tracing:
        middlewares.append(LangfuseTracingMiddleware())
    if self._config.enable_metrics:
        middlewares.append(MetricsMiddleware())
    if self._config.enable_hitl:
        middlewares.append(HITLApprovalMiddleware(sensitive_patterns=...))
    return middlewares
```

**注意**：Worker 的 Middleware 栈**不包含** `skills_aware_prompt`（Worker 有自己的专属系统提示词）。所有 `AgentMiddleware` 子类必须同时提供 sync 和 async 版本（`awrap_model_call`/`awrap_tool_call`），否则在 `astream()`/`ainvoke()` 时抛出 `NotImplementedError`。

### 6.3 _create_worker_agents()

```python
def _create_worker_agents(self) -> Dict[str, object]:
    """为每个 Worker 创建独立的 create_agent 实例。"""
    workers = {}
    worker_middleware = self._build_worker_middleware()
    model_instance = LLMRegistry.get(self._config.model)

    for name, cfg in self._worker_configs.items():
        workers[name] = create_agent(
            model=model_instance,
            tools=self._all_tools,           # 共享工具集
            system_prompt=cfg["system_prompt"], # 专属系统提示词
            middleware=worker_middleware,       # 共享 Middleware 栈
            name=f"{name}_worker",
        )
    return workers
```

### 6.4 _build_graph()

```python
async def _build_graph(self) -> CompiledStateGraph:
    # 1. 加载 MCP 工具
    await self._initialize_mcp_tools()

    # 2. 创建 Worker Agents
    workers = self._create_worker_agents()

    # 3. 构建 Supervisor 系统提示词（含 Worker 描述）
    supervisor_prompt = "You are a Supervisor agent..."

    # 4. 为每个 Worker 创建 handoff tool
    handoff_tools = [transfer_to_researcher, transfer_to_coder, ...]

    # 5. 创建 Supervisor Agent
    supervisor = create_agent(
        model=supervisor_model,
        tools=handoff_tools,
        system_prompt=supervisor_prompt,
        middleware=[LangfuseTracingMiddleware(), MetricsMiddleware()],
        name="supervisor",
    )

    # 6. 构建 StateGraph
    builder = StateGraph(MultiAgentState)
    builder.add_node("supervisor", supervisor_node)
    for worker_name in workers:
        builder.add_node(worker_name, worker_node)
    builder.add_edge(START, "supervisor")

    # 7. 编译（带 Checkpointer）
    graph = builder.compile(checkpointer=checkpointer)
```

---

## 7. 函数调用链

### 7.1 完整请求调用链

```text
POST /api/v1/chatbot/chat?mode=multi
  │
  ▼
chatbot_v1.chat_v1(mode="multi")              # chatbot_v1.py:55
  │
  ├─ get_current_session()                     # JWT 认证
  ├─ _get_agent("multi") → _multi_agent       # 获取 V1MultiAgent 单例
  │
  ▼
V1MultiAgent.get_response(messages, session_id, user_id)  # multi_agent.py:423
  │
  ├─ _build_graph()                            # multi_agent.py:285（首次调用）
  │   ├─ _initialize_mcp_tools()               # 加载 MCP 工具
  │   ├─ _create_worker_agents()               # 创建 3 个 Worker Agent
  │   │   ├─ _build_worker_middleware()         # Worker Middleware 栈
  │   │   ├─ create_agent("researcher", ...)
  │   │   ├─ create_agent("coder", ...)
  │   │   └─ create_agent("analyst", ...)
  │   ├─ 构建 supervisor_prompt               # 含 Worker 描述
  │   ├─ 创建 handoff_tools                    # transfer_to_* 工具
  │   ├─ create_agent(supervisor, handoff_tools)
  │   ├─ StateGraph(MultiAgentState)
  │   │   ├─ add_node("supervisor", supervisor_node)
  │   │   ├─ add_node("researcher", worker_node)
  │   │   ├─ add_node("coder", worker_node)
  │   │   ├─ add_node("analyst", worker_node)
  │   │   └─ add_edge(START, "supervisor")
  │   ├─ AsyncPostgresSaver.setup()
  │   └─ builder.compile(checkpointer)
  │
  ├─ _get_relevant_memory(user_id, query)      # 记忆检索
  │
  ├─ 构建 input_messages（前置 memory system msg）
  │
  ▼
graph.ainvoke({messages}, config)               # Graph 执行
  │
  │  ┌──── supervisor_node ──────────────────────────┐
  │  │                                                │
  │  │  supervisor.ainvoke(state, config)              │
  │  │    → Supervisor LLM 分析请求                    │
  │  │    → 决定调用 transfer_to_coder(request=...)    │
  │  │                                                │
  │  │  扫描响应中的 handoff tool_calls:               │
  │  │    → 找到 transfer_to_coder                     │
  │  │    → Command(goto="coder")                      │
  │  │                                                │
  │  │  如果没有 handoff（通用对话）:                    │
  │  │    → Command(goto=END)                          │
  │  └────────────────────────────────────────────────┘
  │
  │  ┌──── worker_node (coder) ──────────────────────┐
  │  │                                                │
  │  │  coder_agent.ainvoke(state, config)             │
  │  │    │                                           │
  │  │    │  ┌── Worker Middleware ──────────────┐     │
  │  │    │  │ LangfuseTracingMiddleware         │     │
  │  │    │  │ MetricsMiddleware                 │     │
  │  │    │  │ HITLApprovalMiddleware            │     │
  │  │    │  └──────────────────────────────────┘     │
  │  │    │                                           │
  │  │    │  ┌── Agent 内部循环 ──────────────┐       │
  │  │    │  │ LLM 推理 → 工具调用 → 再推理    │       │
  │  │    │  └───────────────────────────────┘       │
  │  │    │                                           │
  │  │  → Command(goto=END)                           │
  │  └────────────────────────────────────────────────┘
  │
  ▼
asyncio.create_task(_update_long_term_memory())
  │
  ▼
_process_messages() → ChatResponse
```

### 7.2 Supervisor 路由决策流程

```text
Supervisor Agent 收到消息
  │
  ├─ 系统提示词包含：
  │   "## Available Workers
  │    - researcher: Research, web search...
  │    - coder: Code writing, debugging...
  │    - analyst: Data analysis, statistics..."
  │
  ├─ 工具列表包含：
  │   - transfer_to_researcher(request: str)
  │   - transfer_to_coder(request: str)
  │   - transfer_to_analyst(request: str)
  │
  ▼
  LLM 推理 → 选择调用 transfer_to_coder("用户想写排序算法")
  │
  ▼
  supervisor_node 捕获:
    for msg in response["messages"]:
      if msg.tool_calls:
        for tc in msg.tool_calls:
          if tc["name"] == "transfer_to_coder":
            return Command(goto="coder")
```

---

## 8. Graph 构建详解

### 8.1 Graph 可视化

```text
            ┌──────────────┐
  START ──→ │  supervisor  │
            └──────┬───────┘
                   │
       ┌───────────┼───────────┐───────────┐
       │           │           │           │
       ▼           ▼           ▼           ▼
 ┌──────────┐ ┌──────────┐ ┌──────────┐  END
 │researcher│ │  coder   │ │ analyst  │ (直接回复)
 └────┬─────┘ └────┬─────┘ └────┬─────┘
      │            │            │
      └────────────┼────────────┘
                   │
                   ▼
                  END
```

### 8.2 节点类型对比

| 节点 | 实现方式 | Agent 类型 | Middleware |
|------|---------|-----------|-----------|
| supervisor | `supervisor_node` 函数 | `create_agent` + handoff tools | 追踪 + 指标 |
| researcher | `worker_node` 函数 | `create_agent` + 全部工具 | 追踪 + 指标 + HITL |
| coder | `worker_node` 函数 | `create_agent` + 全部工具 | 追踪 + 指标 + HITL |
| analyst | `worker_node` 函数 | `create_agent` + 全部工具 | 追踪 + 指标 + HITL |

---

## 9. API 端点

| 方法 | 路径 | 查询参数 | 功能 |
|------|------|---------|------|
| POST | `/api/v1/chatbot/chat` | `mode=multi` | 非流式多 Agent 聊天 |
| POST | `/api/v1/chatbot/chat/stream` | `mode=multi` | 流式多 Agent 聊天 |
| GET | `/api/v1/chatbot/messages` | — | 获取会话历史 |
| DELETE | `/api/v1/chatbot/messages` | — | 清除会话历史 |

---

## 10. 使用示例

### 10.1 路由到 Researcher

```text
用户: "帮我调研一下 2024 年大语言模型的发展趋势"

Supervisor 分析:
  → 涉及信息搜索和调研
  → 调用 transfer_to_researcher("调研 2024 大语言模型发展趋势")

Graph 路由: supervisor → researcher

Researcher Agent:
  → 使用 web_search 工具搜索相关论文和报告
  → 整理并返回结构化研究报告

返回: "## 2024 年 LLM 发展趋势\n1. 多模态融合...\n2. 长上下文窗口..."
```

### 10.2 路由到 Coder

```text
用户: "用 Python 实现一个 LRU Cache"

Supervisor 分析:
  → 明确的编程任务
  → 调用 transfer_to_coder("Python 实现 LRU Cache")

Graph 路由: supervisor → coder

Coder Agent:
  → 直接编写代码（无需工具调用）
  → 包含注释、类型提示和使用示例

返回: "```python\nfrom collections import OrderedDict\n\nclass LRUCache:..."
```

### 10.3 路由到 Analyst

```text
用户: "分析这组销售数据的季度趋势，给出优化建议"

Supervisor 分析:
  → 数据分析任务
  → 调用 transfer_to_analyst("分析销售数据季度趋势")

Graph 路由: supervisor → analyst

Analyst Agent:
  → 分析数据模式
  → 给出统计结论和可视化建议

返回: "## 销售数据分析\n### 季度趋势\nQ1-Q4 增长率分别为..."
```

### 10.4 直接回复（不路由到 Worker）

```text
用户: "你好，今天天气怎么样？"

Supervisor 分析:
  → 简单日常对话，不需要专家
  → 不调用任何 handoff tool，直接回复

Graph 路由: supervisor → END

返回: "你好！我无法获取实时天气信息，但你可以查看天气预报网站..."
```

### 10.5 cURL 示例

```bash
# V1 Multi-Agent - 非流式
curl -X POST "http://localhost:8000/api/v1/chatbot/chat?mode=multi" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Session-Id: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"帮我调研 RAG 技术最新进展"}]}'

# V1 Multi-Agent - 流式
curl -N -X POST "http://localhost:8000/api/v1/chatbot/chat/stream?mode=multi" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Session-Id: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"用 TypeScript 写一个 REST API"}]}'
```

---

## 11. 扩展：添加自定义 Worker

### 11.1 使用 register_worker()

```python
from app.core.langgraph.v1.multi_agent import register_worker

# 注册新 Worker
register_worker(
    name="translator",
    system_prompt=(
        "You are an expert translator. Your strengths:\n"
        "- Multi-language translation with cultural context\n"
        "- Technical document localization\n"
        "- Maintaining tone and style across languages\n\n"
        "Always preserve the original meaning and adapt cultural references."
    ),
    description="Multi-language translation, localization, cultural adaptation",
)
```

注册后，下次 `V1MultiAgent` 初始化时会自动包含新 Worker。

### 11.2 通过配置传入

```python
from app.core.langgraph.v1.multi_agent import V1MultiAgent, V1MultiAgentConfig

custom_workers = {
    "researcher": {...},
    "coder": {...},
    "translator": {
        "system_prompt": "You are an expert translator...",
        "description": "Translation and localization",
    },
}

config = V1MultiAgentConfig(worker_configs=custom_workers)
agent = V1MultiAgent(config=config)
```

### 11.3 Worker 添加后的变化

新 Worker 注册后自动生效的部分：

1. **Supervisor 系统提示词**：自动包含新 Worker 描述
2. **Handoff Tool**：自动创建 `transfer_to_translator`
3. **Graph 节点**：自动添加 `translator` 节点
4. **Middleware**：自动应用共享 Middleware 栈

无需修改 Supervisor 逻辑或 Graph 构建代码。

---

### 相关文档

- [返回功能总览 — NEW_FEATURES_GUIDE.md](./NEW_FEATURES_GUIDE.md#4-agent-模式总览)
- [Single Agent 模式](./AGENT_MODE_2_V1_SINGLE.md)
- [Workflow 编排引擎](./AGENT_MODE_4_WORKFLOW.md)

---

> **文档版本**: 1.0
> **对应源文件**: `app/core/langgraph/v1/multi_agent.py` · `app/api/v1/chatbot_v1.py`
