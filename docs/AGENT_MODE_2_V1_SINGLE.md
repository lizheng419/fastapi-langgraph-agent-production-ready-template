# Agent 模式 2：V1 Single Agent（create_agent + Middleware）

> 本文档详细讲解 V1 Single Agent 模式的实现原理、Middleware 机制、函数调用链、使用方式和示例。

---

## 目录

1. [模式概述](#1-模式概述)
2. [架构图](#2-架构图)
3. [核心文件](#3-核心文件)
4. [Middleware 机制详解](#5-middleware-机制详解)
5. [类与函数详解](#6-类与函数详解)
6. [函数调用链](#7-函数调用链)
7. [API 端点](#8-api-端点)
8. [使用示例](#9-使用示例)
9. [配置与自定义](#10-配置与自定义)
10. [Middleware 扩展指南](#11-middleware-扩展指南)

---

## 1. 模式概述

V1 Single Agent 使用 LangChain v1 的 `create_agent` API 替代手动 `StateGraph` 构建。Agent 循环（LLM 推理 → 工具调用 → 再推理）由框架内部自动处理，开发者通过 **可组合的 Middleware 栈** 注入系统提示词、长期记忆、追踪、指标和 HITL 审批等横切关注点。

| 属性 | 值 |
|------|------|
| **实现类** | `V1Agent` |
| **源文件** | `app/core/langgraph/v1/agent.py` |
| **Middleware** | `app/core/langgraph/v1/middleware.py` |
| **API 前缀** | `/api/v1/chatbot` |
| **路由文件** | `app/api/v1/chatbot_v1.py` |
| **Agent 创建** | `langchain.agents.create_agent()` |
| **关键特性** | Middleware 栈、自动 Agent 循环、HITL、Langfuse 追踪、Prometheus 指标 |

---

## 2. 架构图

```text
用户请求
   │
   ▼
FastAPI 路由 (chatbot_v1.py)
   │  POST /api/v1/chatbot/chat?mode=single
   │  POST /api/v1/chatbot/chat/stream?mode=single
   │
   ▼
V1Agent.get_response() / get_stream_response()
   │
   ├─ _get_relevant_memory()          ← mem0 长期记忆检索
   ├─ 构建 MemoryContext              ← 携带 user_id、session_id、记忆
   │
   ▼
create_agent 实例.ainvoke() / astream()
   │
   │  ┌──────── Middleware 栈（按顺序执行） ────────┐
   │  │                                              │
   │  │  1. SystemPromptMiddleware.before_model()    │
   │  │     → 动态构建系统提示词（Skills + 记忆）     │
   │  │                                              │
   │  │  2. LongTermMemoryMiddleware.before_model()  │
   │  │     → 注入长期记忆上下文                      │
   │  │                                              │
   │  │  3. LangfuseTracingMiddleware.before_model() │
   │  │     → 记录追踪日志                            │
   │  │                                              │
   │  │  4. MetricsMiddleware.wrap_model_call()      │
   │  │     → Prometheus 计时包装                     │
   │  │                                              │
   │  │  5. HITLApprovalMiddleware.wrap_tool_call()  │
   │  │     → 敏感工具拦截审批                        │
   │  │                                              │
   │  └──────────────────────────────────────────────┘
   │
   │  ┌──────── Agent 内部循环（自动管理） ──────────┐
   │  │  LLM 推理 → tool_calls? → 执行工具 → 再推理  │
   │  │  → ... → 无 tool_calls → 返回                 │
   │  └──────────────────────────────────────────────┘
   │
   ▼
_update_long_term_memory()            ← 后台异步更新记忆
   │
   ▼
返回响应给用户
```

---

## 3. 核心文件

| 文件路径 | 职责 |
|---------|------|
| `app/core/langgraph/v1/agent.py` | `V1Agent` 类：Agent 创建、记忆管理、响应处理 |
| `app/core/langgraph/v1/middleware.py` | 5 个 Middleware 实现 + `create_default_middleware()` 工厂函数 |
| `app/api/v1/chatbot_v1.py` | FastAPI 路由：支持 `?mode=single` / `?mode=multi` 切换 |
| `app/services/llm.py` | `LLMRegistry`：模型注册与获取 |
| `app/core/prompts.py` | `load_system_prompt()`：系统提示词模板 |
| `app/core/langgraph/hitl/` | `ApprovalManager`：HITL 审批管理 |

---

## 5. Middleware 机制详解

### 5.1 Middleware 接口

LangChain v1.2+ 的 `AgentMiddleware` 提供以下钩子：

```python
class AgentMiddleware:
    def before_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        """LLM 调用前执行。返回 dict 可修改 agent 状态（如注入 system_prompt）。"""

    def after_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        """LLM 调用后执行。"""

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        """包装 LLM 调用（同步）。可用于计时、日志等。"""

    def wrap_tool_call(self, request: ToolCallRequest, handler) -> ToolMessage | Command:
        """包装工具调用。可用于拦截、审批等。"""
```

### 5.2 五层 Middleware 栈

#### ① SystemPromptMiddleware

```python
class SystemPromptMiddleware(AgentMiddleware):
    def before_model(self, state, runtime):
        ctx = getattr(runtime, "context", None)
        memory_text = getattr(ctx, "relevant_memory", "") if ctx else ""
        system_prompt = load_system_prompt(long_term_memory=memory_text)
        return {"system_prompt": system_prompt}
```

- **触发时机**：每次 LLM 调用前
- **功能**：加载 Skills 描述 + 长期记忆 → 构建完整系统提示词
- **始终启用**（不可通过配置关闭）

#### ② LongTermMemoryMiddleware

```python
class LongTermMemoryMiddleware(AgentMiddleware):
    def before_model(self, state, runtime):
        ctx = getattr(runtime, "context", None)
        memory_text = getattr(ctx, "relevant_memory", "")
        # 记忆已通过 MemoryContext 传入，此处可用于额外处理
        return None
```

- **触发时机**：每次 LLM 调用前
- **功能**：从 `runtime.context` 中读取预检索的记忆

#### ③ LangfuseTracingMiddleware

```python
class LangfuseTracingMiddleware(AgentMiddleware):
    def before_model(self, state, runtime):
        ctx = getattr(runtime, "context", None) if runtime else None
        logger.debug("langfuse_before_model",
            user_id=getattr(ctx, "user_id", None),
            session_id=getattr(ctx, "session_id", None))
        return None
```

- **触发时机**：每次 LLM 调用前
- **功能**：记录 debug 日志，配合 API 层的 `@observe` 和 Langfuse 自动检测

#### ④ MetricsMiddleware

```python
class MetricsMiddleware(AgentMiddleware):
    def wrap_model_call(self, request, handler):
        with llm_inference_duration_seconds.labels(model=settings.DEFAULT_LLM_MODEL).time():
            return handler(request)

    async def awrap_model_call(self, request, handler):
        with llm_inference_duration_seconds.labels(model=settings.DEFAULT_LLM_MODEL).time():
            result = handler(request)
            if hasattr(result, "__await__"):
                return await result
            return result
```

- **触发时机**：包装每次 LLM 调用
- **功能**：Prometheus histogram 自动计时
- 同时提供同步和异步版本

#### ⑤ HITLApprovalMiddleware

```python
class HITLApprovalMiddleware(AgentMiddleware):
    sensitive_patterns = ["delete", "modify", "update", "write", "execute_sql", "send_email"]

    def wrap_tool_call(self, request, handler):
        tool_name = request.tool_call.get("name", "")
        if not self._is_sensitive(tool_name):
            return handler(request)  # 非敏感工具直接执行

        # 敏感工具：返回拦截消息
        return ToolMessage(
            content=f"🔒 Action `{tool_name}` requires human approval...",
            tool_call_id=request.tool_call.get("id", ""),
        )
```

- **触发时机**：每次工具调用
- **功能**：匹配敏感模式 → 拦截执行 → 返回审批提示
- **可自定义模式**：通过 `sensitive_patterns` 参数

### 5.3 Middleware 执行顺序

```text
请求进入
  │
  ▼
SystemPromptMiddleware.before_model()    ← 构建系统提示词
  │
  ▼
LongTermMemoryMiddleware.before_model()  ← 记忆注入
  │
  ▼
LangfuseTracingMiddleware.before_model() ← 追踪日志
  │
  ▼
MetricsMiddleware.wrap_model_call()      ← 开始计时
  │  ┌─────────────────────┐
  │  │   LLM 推理执行       │
  │  └─────────────────────┘
  │                                       ← 结束计时
  ▼
如果有 tool_calls:
  HITLApprovalMiddleware.wrap_tool_call() ← 检查是否需要审批
  │  ├─ 非敏感 → 正常执行工具
  │  └─ 敏感 → 返回审批消息
  ▼
继续 Agent 循环或返回
```

---

## 6. 类与函数详解

### 6.1 V1AgentConfig

```python
@dataclass
class V1AgentConfig:
    model: str = settings.DEFAULT_LLM_MODEL   # 使用的 LLM 模型
    enable_hitl: bool = True                    # 启用 HITL 审批
    enable_memory: bool = True                  # 启用长期记忆
    enable_tracing: bool = True                 # 启用 Langfuse 追踪
    enable_metrics: bool = True                 # 启用 Prometheus 指标
    sensitive_patterns: Optional[List[str]] = None  # 自定义敏感模式
```

### 6.2 MemoryContext

```python
@dataclass
class MemoryContext:
    user_id: str = ""
    session_id: str = ""
    relevant_memory: str = ""
```

- 作为 `context_schema` 传入 `create_agent()`
- Middleware 通过 `runtime.context` 访问

### 6.3 V1Agent._create_agent()

```python
async def _create_agent(self):
    # 1. 加载 MCP 工具
    await self._initialize_mcp_tools()

    # 2. 构建 Middleware 栈
    middleware = create_default_middleware(
        enable_hitl=self._config.enable_hitl,
        enable_memory=self._config.enable_memory,
        enable_tracing=self._config.enable_tracing,
        enable_metrics=self._config.enable_metrics,
        sensitive_patterns=self._config.sensitive_patterns,
    )

    # 3. 设置 Checkpointer
    connection_pool = await self._get_connection_pool()
    checkpointer = AsyncPostgresSaver(connection_pool)
    await checkpointer.setup()

    # 4. 创建 Agent（核心调用）
    model_instance = LLMRegistry.get(self._config.model)
    self._agent = create_agent(
        model=model_instance,          # LLM 模型实例
        tools=self._all_tools,         # 内置 + MCP 工具
        middleware=middleware,          # Middleware 栈
        checkpointer=checkpointer,     # PostgreSQL 持久化
        context_schema=MemoryContext,   # 运行时上下文类型
        name="V1 Agent",               # Agent 名称
    )
```

**关键区别**：不再手动构建 `StateGraph`，`create_agent()` 自动处理：
- Agent 循环（LLM → 工具 → LLM → ...）
- 消息状态管理
- 工具调用 → ToolMessage → 再推理

### 6.4 V1Agent.get_response()

```python
async def get_response(self, messages, session_id, user_id=None):
    # 1. 确保 Agent 已创建
    if self._agent is None:
        await self._create_agent()

    # 2. 检索记忆
    relevant_memory = await self._get_relevant_memory(user_id, messages[-1].content)

    # 3. 构建运行时上下文
    context = MemoryContext(
        user_id=user_id or "",
        session_id=session_id,
        relevant_memory=relevant_memory,
    )

    # 4. 构建 config
    config = {
        "configurable": {"thread_id": session_id},
        "metadata": {"user_id": user_id, "session_id": session_id, ...},
    }

    # 5. 调用 Agent
    response = await self._agent.ainvoke(
        {"messages": input_messages},
        config=config,
        context=context,    # ← MemoryContext 传递给 Middleware
    )

    # 6. 后台更新记忆
    asyncio.create_task(self._update_long_term_memory(...))

    # 7. 格式化输出
    return self._process_messages(response["messages"])
```

---

## 7. 函数调用链

### 7.1 非流式请求完整调用链

```text
POST /api/v1/chatbot/chat?mode=single
  │
  ▼
chatbot_v1.chat_v1()                            # chatbot_v1.py:55
  │
  ├─ get_current_session()                       # JWT 认证
  ├─ _get_agent("single") → _single_agent       # 获取 V1Agent 单例
  │
  ▼
V1Agent.get_response(messages, session_id, user_id)  # agent.py:237
  │
  ├─ _create_agent()                             # agent.py:194（首次调用）
  │   ├─ _initialize_mcp_tools()                 # 加载 MCP 工具
  │   ├─ create_default_middleware()              # middleware.py:228
  │   │   ├─ SystemPromptMiddleware()
  │   │   ├─ LongTermMemoryMiddleware()
  │   │   ├─ LangfuseTracingMiddleware()
  │   │   ├─ MetricsMiddleware()
  │   │   └─ HITLApprovalMiddleware()
  │   ├─ _get_connection_pool()                  # PostgreSQL 连接
  │   ├─ AsyncPostgresSaver.setup()              # Checkpoint 表
  │   ├─ LLMRegistry.get(model)                  # 获取 LLM 实例
  │   └─ create_agent(model, tools, middleware, checkpointer, context_schema)
  │
  ├─ _get_relevant_memory(user_id, query)        # agent.py:171
  │   └─ mem0.search()
  │
  ├─ MemoryContext(user_id, session_id, relevant_memory)
  │
  ▼
agent.ainvoke({messages}, config, context)       # LangChain v1 Agent 执行
  │
  │  ┌──── Middleware 执行 ────────────────────┐
  │  │ SystemPromptMiddleware.before_model()   │ → 动态系统提示词
  │  │ LongTermMemoryMiddleware.before_model() │ → 记忆注入
  │  │ LangfuseTracingMiddleware.before_model()│ → 追踪
  │  │ MetricsMiddleware.wrap_model_call()     │ → Prometheus 计时
  │  └────────────────────────────────────────┘
  │
  │  ┌──── Agent 内部循环（自动） ─────────────┐
  │  │ LLM 推理 → 有 tool_calls?              │
  │  │   → HITLApprovalMiddleware 检查         │
  │  │   → 执行工具 → ToolMessage              │
  │  │   → 再次推理 → ... → 无 tool_calls     │
  │  └────────────────────────────────────────┘
  │
  ▼
asyncio.create_task(_update_long_term_memory())  # 后台更新
  │
  ▼
_process_messages() → ChatResponse               # 格式化返回
```

### 7.2 流式请求调用链

```text
POST /api/v1/chatbot/chat/stream?mode=single
  │
  ▼
chatbot_v1.chat_stream_v1()                      # chatbot_v1.py:97
  │
  ▼
StreamingResponse(event_generator())              # SSE 流
  │
  ▼
V1Agent.get_stream_response(messages, session_id, user_id)  # agent.py:304
  │
  ├─ _create_agent()                              # 同上
  ├─ _get_relevant_memory()                       # 同上
  ├─ MemoryContext(...)                            # 同上
  │
  ▼
agent.astream({messages}, config, context, stream_mode="messages")
  │
  │  ┌──── Middleware + Agent 循环 ──────────────┐
  │  │ （同非流式，但以 token 粒度输出）          │
  │  └────────────────────────────────────────────┘
  │
  │  每个 token:
  │  yield f"data: {json.dumps({content, done=False})}\n\n"
  │
  ▼
流结束:
  ├─ agent.get_state(config) 获取最终状态
  ├─ asyncio.create_task(_update_long_term_memory())
  └─ yield f"data: {json.dumps({content='', done=True})}\n\n"
```

---

## 8. API 端点

| 方法 | 路径 | 查询参数 | 功能 |
|------|------|---------|------|
| POST | `/api/v1/chatbot/chat` | `mode=single` | 非流式聊天 |
| POST | `/api/v1/chatbot/chat/stream` | `mode=single` | 流式聊天（SSE） |
| GET | `/api/v1/chatbot/messages` | — | 获取会话历史 |
| DELETE | `/api/v1/chatbot/messages` | — | 清除会话历史 |

> **注意**：`mode=multi` 会切换到 V1MultiAgent（见模式 3 文档）。默认为 `single`。

---

## 9. 使用示例

### 9.1 简单对话

```text
用户: "解释一下 Python 的装饰器"

Middleware 执行:
  SystemPromptMiddleware → 加载 Skills + 记忆 → 系统提示词
  MetricsMiddleware → 开始计时

Agent 内部:
  LLM 推理 → 无 tool_calls → 直接返回

  MetricsMiddleware → 记录耗时到 Prometheus

返回: "Python 装饰器是一种语法糖..."
```

### 9.2 带工具调用 + HITL 拦截

```text
用户: "删除数据库中 ID 为 123 的用户"

Middleware 执行:
  SystemPromptMiddleware → 系统提示词
  MetricsMiddleware → 计时

Agent 内部:
  LLM 推理 → tool_calls: [delete_user(id=123)]
  HITLApprovalMiddleware.wrap_tool_call():
    → "delete" 匹配 sensitive_patterns
    → 返回 ToolMessage("🔒 Action `delete_user` requires human approval...")
  LLM 收到审批消息 → 生成友好回复

返回: "该操作需要人工审批。请通过审批 API 进行批准。"
```

### 9.3 cURL 示例

```bash
# V1 Single Agent - 非流式
curl -X POST "http://localhost:8000/api/v1/chatbot/chat?mode=single" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Session-Id: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"用 Python 写一个二分查找"}]}'

# V1 Single Agent - 流式
curl -N -X POST "http://localhost:8000/api/v1/chatbot/chat/stream?mode=single" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Session-Id: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"解释量子计算"}]}'
```

---

## 10. 配置与自定义

### 10.1 V1AgentConfig 参数

```python
from app.core.langgraph.v1.agent import V1Agent, V1AgentConfig

# 自定义配置
config = V1AgentConfig(
    model="gpt-4o",                    # 使用更强的模型
    enable_hitl=True,                   # 启用 HITL
    enable_memory=True,                 # 启用长期记忆
    enable_tracing=True,                # 启用 Langfuse
    enable_metrics=True,                # 启用 Prometheus
    sensitive_patterns=["delete", "drop", "truncate"],  # 自定义敏感模式
)

agent = V1Agent(config=config)
```

### 10.2 禁用特定 Middleware

```python
# 轻量模式：只保留系统提示词
config = V1AgentConfig(
    enable_hitl=False,
    enable_memory=False,
    enable_tracing=False,
    enable_metrics=False,
)
```

此时 Middleware 栈仅包含 `SystemPromptMiddleware`（始终启用）。

---

## 11. Middleware 扩展指南

### 11.1 创建自定义 Middleware

```python
# app/core/langgraph/v1/middleware.py

class RateLimitMiddleware(AgentMiddleware):
    """限制单个用户的 LLM 调用频率。"""

    def __init__(self, max_calls_per_minute: int = 10):
        super().__init__()
        self.max_calls = max_calls_per_minute
        self._call_counts = {}

    def before_model(self, state: AgentState, runtime: Runtime) -> dict | None:
        ctx = getattr(runtime, "context", None)
        user_id = getattr(ctx, "user_id", "unknown") if ctx else "unknown"

        # 检查调用频率
        count = self._call_counts.get(user_id, 0)
        if count >= self.max_calls:
            logger.warning("rate_limit_exceeded", user_id=user_id)
            # 可以抛出异常或返回修改后的状态
        self._call_counts[user_id] = count + 1
        return None
```

### 11.2 注册到 Middleware 栈

```python
def create_default_middleware(...) -> List[AgentMiddleware]:
    middlewares = []
    middlewares.append(SystemPromptMiddleware())  # 始终启用

    # 添加自定义 Middleware
    middlewares.append(RateLimitMiddleware(max_calls_per_minute=20))

    if enable_memory:
        middlewares.append(LongTermMemoryMiddleware())
    # ... 其余 Middleware
    return middlewares
```

### 11.3 Middleware 钩子选择指南

| 需求 | 使用钩子 | 示例 |
|------|---------|------|
| 修改系统提示词 | `before_model` | SystemPromptMiddleware |
| 记录调用日志 | `before_model` / `after_model` | LangfuseTracingMiddleware |
| 包装 LLM 调用（计时、重试） | `wrap_model_call` | MetricsMiddleware |
| 拦截工具执行 | `wrap_tool_call` | HITLApprovalMiddleware |
| 修改 LLM 返回结果 | `after_model` | （自定义后处理） |

---

### 相关文档

- [返回功能总览 — NEW_FEATURES_GUIDE.md](./NEW_FEATURES_GUIDE.md#4-agent-模式总览)
- [Multi-Agent 模式](./AGENT_MODE_3_V1_MULTI.md)
- [Workflow 编排引擎](./AGENT_MODE_4_WORKFLOW.md)

---

> **文档版本**: 1.0
> **对应源文件**: `app/core/langgraph/v1/agent.py` · `app/core/langgraph/v1/middleware.py` · `app/api/v1/chatbot_v1.py`
