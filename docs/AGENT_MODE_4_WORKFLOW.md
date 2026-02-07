# Agent 模式 4：Workflow（Orchestrator-Worker + Send）

> 本文档详细讲解 Workflow Agent 模式的实现原理、Send API 并行执行机制、Planner 规划、函数调用链、使用方式和示例。

---

## 目录

1. [模式概述](#1-模式概述)
2. [架构图](#2-架构图)
3. [核心文件](#3-核心文件)
4. [核心概念](#4-核心概念)
5. [状态定义](#5-状态定义)
6. [Planner 规划器](#6-planner-规划器)
7. [Graph 节点详解](#7-graph-节点详解)
8. [函数调用链](#8-函数调用链)
9. [Graph 构建详解](#9-graph-构建详解)
10. [API 端点](#10-api-端点)
11. [使用示例](#11-使用示例)
12. [YAML 模板系统](#12-yaml-模板系统)
13. [扩展指南](#13-扩展指南)
14. [与其他模式对比](#14-与其他模式对比)

---

## 1. 模式概述

Workflow 模式使用 **Orchestrator-Worker** 模式，将复杂任务拆解为多步骤执行计划，通过 LangGraph 的 **Send API** 实现步骤的并行/串行调度。适用于需要多个专家协作、有依赖关系的复杂任务。

| 属性 | 值 |
|------|------|
| **实现类** | `WorkflowGraph` |
| **源文件** | `app/core/langgraph/workflow/graph.py` |
| **Planner** | `app/core/langgraph/workflow/planner.py` |
| **Schema** | `app/core/langgraph/workflow/schema.py` |
| **API 前缀** | `/api/v1/chatbot/workflow` |
| **路由文件** | `app/api/v1/chatbot_workflow.py` |
| **关键特性** | Send API 并行执行、依赖链调度、YAML 模板、LLM 动态规划 |

---

## 2. 架构图

```text
用户请求
   │
   ▼
FastAPI 路由 (chatbot_workflow.py)
   │  POST /api/v1/chatbot/workflow/chat
   │  POST /api/v1/chatbot/workflow/chat/stream
   │
   ▼
WorkflowGraph.get_response()
   │
   ▼
CompiledStateGraph.ainvoke()
   │
   │  ┌──────────────────────────────────────────────────────────────┐
   │  │                                                              │
   │  │  [planner] 节点                                              │
   │  │    │  ├─ 匹配 YAML 模板                                      │
   │  │    │  └─ 或 LLM 动态生成多步骤计划                             │
   │  │    │                                                          │
   │  │    ▼                                                          │
   │  │  _assign_workers (条件边)                                     │
   │  │    │  → 使用 Send API 分发可执行步骤                            │
   │  │    │                                                          │
   │  │    ▼                                                          │
   │  │  [worker_task] 节点 ×N (并行)                                 │
   │  │    │  每个 Worker 独立执行，结果写入 completed_results          │
   │  │    │                                                          │
   │  │    ▼                                                          │
   │  │  [check_completion] 节点                                      │
   │  │    │  ├─ 还有未完成步骤 → 回到 _assign_workers（下一轮）       │
   │  │    │  └─ 全部完成 → [synthesizer]                             │
   │  │    │                                                          │
   │  │    ▼                                                          │
   │  │  [synthesizer] 节点                                           │
   │  │    │  汇总所有 Worker 结果 → 生成最终输出                       │
   │  │    │                                                          │
   │  │    ▼                                                          │
   │  │   END                                                         │
   │  │                                                              │
   │  └──────────────────────────────────────────────────────────────┘
   │
   ▼
返回响应给用户
```

---

## 3. 核心文件

| 文件路径 | 职责 |
|---------|------|
| `app/core/langgraph/workflow/graph.py` | `WorkflowGraph`：Graph 构建、节点实现、公开 API |
| `app/core/langgraph/workflow/planner.py` | `WorkflowPlanner`：YAML 模板匹配 + LLM 动态规划 |
| `app/core/langgraph/workflow/schema.py` | 状态模型：`WorkflowState`、`WorkerTaskState`、`WorkflowPlan`、`WorkflowStep` |
| `app/core/langgraph/workflow/templates/` | YAML 模板文件目录（自动加载） |
| `app/api/v1/chatbot_workflow.py` | FastAPI 路由：`/chat`、`/chat/stream`、`/templates` |
| `app/core/langgraph/agents/workers.py` | `WORKER_REGISTRY`：Worker 实例注册表 |

---

## 4. 核心概念

### 4.1 Send API

LangGraph 的 `Send` API 允许从一个节点**动态扇出**多个并行任务，每个任务有独立的状态：

```python
from langgraph.types import Send

# 分发 3 个并行任务
sends = [
    Send("worker_task", {"step": step_1, "messages": msgs}),
    Send("worker_task", {"step": step_2, "messages": msgs}),
    Send("worker_task", {"step": step_3, "messages": msgs}),
]
```

每个 `Send` 创建一个独立的 `worker_task` 节点实例，并行执行后结果通过 `operator.add` reducer 合并回主状态。

### 4.2 依赖链与多轮调度

```text
步骤 A (无依赖) ─┐
步骤 B (无依赖) ─┤──→ 第 1 轮并行执行
步骤 C (依赖 A) ─┘
                        ↓
                  check_completion
                  → 步骤 C 依赖已满足
                        ↓
步骤 C ──────────────→ 第 2 轮执行
                        ↓
                  check_completion
                  → 全部完成 → synthesizer
```

### 4.3 operator.add Reducer

```python
# WorkflowState 和 WorkerTaskState 中
completed_results: Annotated[list, operator.add] = Field(default_factory=list)
```

多个并行 Worker 的结果通过 `operator.add` 自动合并到父状态的 `completed_results` 列表中。

---

## 5. 状态定义

### 5.1 WorkflowState（主 Graph 状态）

```python
class WorkflowState(BaseModel):
    messages: Annotated[list, add_messages]       # 对话消息
    long_term_memory: str = ""                     # 长期记忆（预留）
    plan: Optional[WorkflowPlan] = None            # 执行计划
    completed_results: Annotated[list, operator.add]  # 已完成结果（reducer 合并）
    current_round: int = 0                         # 当前执行轮次
    final_output: str = ""                         # 最终综合输出
```

### 5.2 WorkerTaskState（单 Worker 隔离状态）

```python
class WorkerTaskState(BaseModel):
    step: WorkflowStep                             # 要执行的步骤
    messages: list                                 # 原始对话上下文
    completed_results: Annotated[list, operator.add]  # Worker 输出
    context_from_deps: str = ""                    # 依赖步骤的结果上下文
```

每个 Worker 通过 Send 接收独立的 `WorkerTaskState`，执行后将结果写入 `completed_results`，由 reducer 合并回主 `WorkflowState`。

### 5.3 WorkflowStep（步骤定义）

```python
class WorkflowStep(BaseModel):
    id: str              # 步骤 ID（如 "step_1"）
    worker: str          # Worker 名（如 "researcher"、"coder"）
    task: str            # 任务描述
    depends_on: list[str] = []  # 依赖的步骤 ID
```

### 5.4 WorkflowPlan（执行计划）

```python
class WorkflowPlan(BaseModel):
    name: str = "dynamic"     # 计划名称
    steps: list[WorkflowStep] # 步骤列表
    reasoning: str = ""        # 规划理由
```

---

## 6. Planner 规划器

### 6.1 规划优先级

```text
1. 显式模板名 → 匹配 YAML 模板
2. 无匹配 → LLM 动态生成计划
3. LLM 失败 → 回退到单步骤 coder Worker
```

### 6.2 LLM 动态规划

```python
class WorkflowPlanner:
    async def plan(self, user_message, template_name=None):
        # 优先级 1：显式模板匹配
        if template_name:
            template = workflow_template_registry.get(template_name)
            if template:
                return self._inject_user_context(template, user_message)

        # 优先级 2：LLM 动态规划
        return await self._llm_plan(user_message)
```

### 6.3 LLM 规划提示词

Planner 的系统提示词包含：
- 可用 Worker 列表及描述
- 可用 YAML 模板列表
- 输出格式要求（JSON）
- 规划规则（2-5 步、每步聚焦、依赖关系）

### 6.4 LLM 规划输出示例

```json
{
  "name": "research_and_implement",
  "reasoning": "用户需要先调研再编码",
  "steps": [
    {"id": "step_1", "worker": "researcher", "task": "调研 LRU Cache 最佳实践", "depends_on": []},
    {"id": "step_2", "worker": "coder", "task": "基于调研结果实现 LRU Cache", "depends_on": ["step_1"]}
  ]
}
```

### 6.5 回退策略

```python
async def _llm_plan(self, user_message):
    try:
        response = await self.llm_service.call(planning_messages)
        # ... 解析 JSON
    except Exception as e:
        # 回退：单步 coder Worker
        return WorkflowPlan(
            name="fallback",
            steps=[WorkflowStep(id="step_1", worker="coder", task=user_message)],
            reasoning=f"Planning failed, falling back to single coder worker.",
        )
```

---

## 7. Graph 节点详解

### 7.1 _planner_node — 规划节点

```python
async def _planner_node(self, state: WorkflowState, config: RunnableConfig) -> dict:
    # 1. 从 state.messages 提取最后一条用户消息
    # 2. 从 config.metadata 获取 template_name（可选）
    # 3. await self.planner.plan(user_message, template_name)
    # 4. 返回 {"plan": plan, "current_round": 0}
```

### 7.2 _assign_workers — 条件边（Send 分发）

```python
def _assign_workers(self, state: WorkflowState) -> list[Send]:
    # 1. 计算已完成步骤 ID 集合
    completed_ids = {r["step_id"] for r in state.completed_results}

    # 2. 获取当前轮次可执行的步骤（依赖已满足）
    eligible_steps = self._get_steps_for_round(state.plan, state.current_round, completed_ids)

    # 3. 如果没有可执行步骤 → 发送到 synthesizer
    if not eligible_steps:
        return [Send("synthesizer", state)]

    # 4. 为每个可执行步骤构建依赖上下文
    for step in eligible_steps:
        dep_context = ""  # 从 completed_results 获取依赖步骤的输出
        sends.append(Send("worker_task", {
            "step": step.model_dump(),
            "messages": state.messages,
            "context_from_deps": dep_context,
        }))

    return sends  # 并行分发
```

**关键逻辑**：`_get_steps_for_round()` 检查每个步骤的 `depends_on` 列表，只有所有依赖步骤都在 `completed_ids` 中的步骤才会被分发。

### 7.3 _worker_task_node — Worker 执行节点

```python
async def _worker_task_node(self, state: WorkerTaskState) -> dict:
    step = WorkflowStep(**state.step)
    worker = WORKER_REGISTRY.get(step.worker)

    # 1. 构建任务提示词（原始任务 + 依赖步骤上下文）
    task_prompt = step.task
    if state.context_from_deps:
        task_prompt += f"\n\n## Context from previous steps\n{state.context_from_deps}"

    # 2. 调用 Worker
    worker_messages = [HumanMessage(content=task_prompt)]
    response = await worker.invoke(worker_messages)

    # 3. 返回结果（通过 operator.add 合并回主状态）
    return {
        "completed_results": [{
            "step_id": step.id,
            "worker": step.worker,
            "task": step.task,
            "output": response.content,
        }]
    }
```

### 7.4 _check_completion_node — 完成检查节点

```python
async def _check_completion_node(self, state: WorkflowState) -> dict:
    completed_ids = {r["step_id"] for r in state.completed_results}
    all_step_ids = {s.id for s in state.plan.steps}
    remaining = all_step_ids - completed_ids

    if remaining:
        # 还有未完成步骤 → 递增轮次
        return {"current_round": state.current_round + 1}

    # 全部完成
    return {}
```

### 7.5 _route_after_check — 完成后路由

```python
def _route_after_check(self, state: WorkflowState) -> list[Send] | str:
    completed_ids = {r["step_id"] for r in state.completed_results}
    all_step_ids = {s.id for s in state.plan.steps}

    if completed_ids >= all_step_ids:
        return "synthesizer"  # 全部完成

    # 扇出下一轮可执行步骤
    return self._assign_workers(state)
```

### 7.6 _synthesizer_node — 综合节点

```python
async def _synthesizer_node(self, state: WorkflowState) -> dict:
    # 1. 遍历所有 completed_results
    # 2. 按步骤 ID 和 Worker 名组织
    # 3. 生成结构化 Markdown 报告

    final_output = f"# Workflow Results: {plan_name}\n*Completed {step_count} steps*\n\n{combined}"

    return {
        "final_output": final_output,
        "messages": [AIMessage(content=final_output)],
    }
```

输出格式：

```markdown
# Workflow Results: research_and_implement
*Completed 2 steps*

### Step: step_1 (Worker: researcher)
**Task**: 调研 LRU Cache 最佳实践
[研究内容...]

---

### Step: step_2 (Worker: coder)
**Task**: 基于调研结果实现 LRU Cache
[代码实现...]
```

---

## 8. 函数调用链

### 8.1 完整请求调用链

```text
POST /api/v1/chatbot/workflow/chat
  │
  ▼
chatbot_workflow.workflow_chat()                # chatbot_workflow.py:37
  │
  ├─ get_current_session()                      # JWT 认证
  ├─ template = Query(default=None)             # 可选模板名
  │
  ▼
workflow_graph.get_response(messages, session_id, user_id, template_name)
  │                                             # graph.py:414
  ├─ create_graph()                             # graph.py:346（首次调用）
  │   ├─ StateGraph(WorkflowState)
  │   ├─ add_node("planner", _planner_node)
  │   ├─ add_node("worker_task", _worker_task_node)
  │   ├─ add_node("check_completion", _check_completion_node)
  │   ├─ add_node("synthesizer", _synthesizer_node)
  │   ├─ add_edge(START, "planner")
  │   ├─ add_conditional_edges("planner", _assign_workers)
  │   ├─ add_edge("worker_task", "check_completion")
  │   ├─ add_conditional_edges("check_completion", _route_after_check)
  │   ├─ add_edge("synthesizer", END)
  │   ├─ AsyncPostgresSaver.setup()
  │   └─ builder.compile(checkpointer)
  │
  ▼
graph.ainvoke({messages}, config)                # Graph 执行
  │
  │  ═══════ 第 1 阶段：规划 ═══════
  │
  │  _planner_node(state, config)                # graph.py:78
  │    ├─ 提取用户消息
  │    ├─ planner.plan(user_message, template_name)  # planner.py:70
  │    │   ├─ 匹配 YAML 模板 → _inject_user_context()
  │    │   └─ 或 LLM 动态规划 → _llm_plan()
  │    └─ 返回 {"plan": WorkflowPlan, "current_round": 0}
  │
  │  ═══════ 第 2 阶段：第 1 轮分发 ═══════
  │
  │  _assign_workers(state) → list[Send]          # graph.py:122
  │    ├─ 计算 eligible_steps（无依赖的步骤）
  │    ├─ Send("worker_task", {step_1, messages})
  │    └─ Send("worker_task", {step_2, messages})  # 并行
  │
  │  ═══════ 第 3 阶段：Worker 并行执行 ═══════
  │
  │  _worker_task_node(state_1)                    # graph.py:168
  │    ├─ WORKER_REGISTRY["researcher"]
  │    ├─ worker.invoke([HumanMessage(task)])
  │    └─ → {"completed_results": [{step_1 result}]}
  │
  │  _worker_task_node(state_2)                    # 并行
  │    ├─ WORKER_REGISTRY["coder"]
  │    ├─ worker.invoke([HumanMessage(task)])
  │    └─ → {"completed_results": [{step_2 result}]}
  │
  │  ═══════ completed_results 通过 operator.add 合并 ═══════
  │
  │  ═══════ 第 4 阶段：完成检查 ═══════
  │
  │  _check_completion_node(state)                 # graph.py:257
  │    ├─ remaining = all_step_ids - completed_ids
  │    ├─ 如有剩余 → {"current_round": 1}
  │    └─ 全部完成 → {}
  │
  │  _route_after_check(state)                     # graph.py:398
  │    ├─ 有剩余 → _assign_workers()（第 2 轮 Send）
  │    └─ 全部完成 → "synthesizer"
  │
  │  ═══════ 第 5 阶段（如需）：第 2 轮分发 ═══════
  │
  │  （重复第 2-4 阶段，处理有依赖的步骤）
  │
  │  ═══════ 最终阶段：综合 ═══════
  │
  │  _synthesizer_node(state)                      # graph.py:281
  │    ├─ 遍历 completed_results
  │    ├─ 生成 Markdown 报告
  │    └─ → {"final_output": ..., "messages": [AIMessage(...)]}
  │
  ▼
_process_messages() → ChatResponse
```

### 8.2 多轮调度示例

假设计划有 3 个步骤，依赖关系为：`step_3 depends_on [step_1]`

```text
Round 0:
  eligible: [step_1, step_2]  (无依赖)
  Send("worker_task", step_1)  ──┐
  Send("worker_task", step_2)  ──┤── 并行执行
                                 ▼
  check_completion:
    completed = {step_1, step_2}
    remaining = {step_3}
    → current_round = 1

Round 1:
  eligible: [step_3]  (step_1 已完成，依赖满足)
  Send("worker_task", step_3, context_from_deps="step_1 的结果")
                                 ▼
  check_completion:
    completed = {step_1, step_2, step_3}
    remaining = {}
    → synthesizer

Synthesizer:
  合并 3 个步骤的结果 → 最终报告
```

---

## 9. Graph 构建详解

### 9.1 Graph 可视化

```text
                  ┌──────────┐
       START ──→  │ planner  │
                  └────┬─────┘
                       │
                  _assign_workers (条件边 + Send)
                       │
            ┌──────────┼──────────┐
            │          │          │
            ▼          ▼          ▼
       ┌─────────┐ ┌─────────┐ ┌─────────┐
       │worker(1)│ │worker(2)│ │worker(3)│   ← 并行 Send
       └────┬────┘ └────┬────┘ └────┬────┘
            │          │          │
            └──────────┼──────────┘
                       │
               ┌───────────────┐
               │check_completion│
               └───────┬───────┘
                       │
              ┌────────┴────────┐
              │                 │
         有剩余步骤         全部完成
              │                 │
              ▼                 ▼
      _assign_workers     ┌─────────────┐
      (回到并行 Send)      │ synthesizer │
                          └──────┬──────┘
                                 │
                                END
```

### 9.2 边定义

```python
builder.add_edge(START, "planner")
builder.add_conditional_edges("planner", self._assign_workers, ["worker_task", "synthesizer"])
builder.add_edge("worker_task", "check_completion")
builder.add_conditional_edges("check_completion", self._route_after_check, ["worker_task", "synthesizer"])
builder.add_edge("synthesizer", END)
```

---

## 10. API 端点

| 方法 | 路径 | 查询参数 | 功能 |
|------|------|---------|------|
| POST | `/api/v1/chatbot/workflow/chat` | `template` (可选) | 非流式 Workflow 执行 |
| POST | `/api/v1/chatbot/workflow/chat/stream` | `template` (可选) | 流式 Workflow 执行 |
| GET | `/api/v1/chatbot/workflow/templates` | — | 列出可用模板 |

---

## 11. 使用示例

### 11.1 LLM 动态规划 — 调研 + 编码

```text
用户: "帮我调研 Redis 缓存策略，然后用 Python 实现一个智能缓存层"

Planner LLM 生成计划:
{
  "name": "research_and_implement",
  "steps": [
    {"id": "step_1", "worker": "researcher", "task": "调研 Redis 缓存策略...", "depends_on": []},
    {"id": "step_2", "worker": "coder", "task": "实现 Python 智能缓存层...", "depends_on": ["step_1"]}
  ]
}

执行:
  Round 0: researcher 执行 step_1（调研）
  Round 1: coder 执行 step_2（编码，使用 step_1 的调研结果作为上下文）
  Synthesizer: 合并调研报告 + 代码实现

返回:
  # Workflow Results: research_and_implement
  ### Step: step_1 (Worker: researcher)
  [Redis 缓存策略调研报告...]
  ---
  ### Step: step_2 (Worker: coder)
  [Python 缓存层代码实现...]
```

### 11.2 并行执行 — 多维度分析

```text
用户: "对比分析 PostgreSQL 和 MongoDB 的性能、安全性和成本"

Planner 生成计划:
{
  "name": "parallel_comparison",
  "steps": [
    {"id": "perf", "worker": "researcher", "task": "分析性能对比...", "depends_on": []},
    {"id": "security", "worker": "researcher", "task": "分析安全性对比...", "depends_on": []},
    {"id": "cost", "worker": "analyst", "task": "分析成本对比...", "depends_on": []},
    {"id": "summary", "worker": "analyst", "task": "综合总结...", "depends_on": ["perf", "security", "cost"]}
  ]
}

执行:
  Round 0: 3 个并行 → perf, security, cost
  Round 1: summary（使用前 3 步结果）
  Synthesizer: 最终报告

返回: 结构化的多维度对比分析报告
```

### 11.3 使用 YAML 模板

```bash
# 指定模板
curl -X POST "http://localhost:8000/api/v1/chatbot/workflow/chat?template=code_review" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Session-Id: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Review this Python code: def foo(x): return x*2"}]}'
```

### 11.4 列出可用模板

```bash
curl http://localhost:8000/api/v1/chatbot/workflow/templates \
  -H "Authorization: Bearer $TOKEN"

# 响应
{
  "templates": [
    {"name": "code_review", "description": "Multi-step code review workflow"},
    {"name": "research_report", "description": "Research and report generation"}
  ]
}
```

### 11.5 cURL 完整示例

```bash
# 非流式 Workflow（自动规划）
curl -X POST http://localhost:8000/api/v1/chatbot/workflow/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Session-Id: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"调研 LangGraph 框架并写一个 demo"}]}'

# 流式 Workflow
curl -N -X POST http://localhost:8000/api/v1/chatbot/workflow/chat/stream \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Session-Id: $SESSION" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"分析 FastAPI vs Flask 的性能差异"}]}'
```

---

## 12. YAML 模板系统

### 12.1 模板目录

```text
app/core/langgraph/workflow/templates/
├── __init__.py               # WorkflowTemplateRegistry 自动加载
├── code_review.yaml           # 代码审查模板
└── research_report.yaml       # 调研报告模板
```

### 12.2 模板格式

```yaml
# app/core/langgraph/workflow/templates/code_review.yaml
name: code_review
description: Multi-step code review workflow
reasoning: Systematic code review with security, performance, and style checks

steps:
  - id: security_check
    worker: coder
    task: "Review the code for security vulnerabilities"
    depends_on: []

  - id: performance_check
    worker: coder
    task: "Review the code for performance issues"
    depends_on: []

  - id: style_check
    worker: coder
    task: "Review code style and best practices"
    depends_on: []

  - id: summary
    worker: analyst
    task: "Synthesize all review findings into a comprehensive report"
    depends_on: [security_check, performance_check, style_check]
```

### 12.3 添加自定义模板

在 `templates/` 目录创建新 `.yaml` 文件即可，启动时自动加载。

```yaml
# templates/data_pipeline.yaml
name: data_pipeline
description: Design and implement a data pipeline
reasoning: Research best practices, design architecture, implement code

steps:
  - id: research
    worker: researcher
    task: "Research data pipeline best practices and tools"
    depends_on: []

  - id: design
    worker: analyst
    task: "Design the pipeline architecture based on research"
    depends_on: [research]

  - id: implement
    worker: coder
    task: "Implement the data pipeline based on the design"
    depends_on: [design]
```

---

## 13. 扩展指南

### 13.1 添加新 Worker

Workflow 模式使用 `WORKER_REGISTRY`（`app/core/langgraph/agents/workers.py`），添加新 Worker 即可在 Workflow 中使用：

```python
# app/core/langgraph/agents/workers.py

class DevOpsWorker(BaseWorker):
    name = "devops"
    description = "Infrastructure, CI/CD, deployment, monitoring"
    system_prompt = "You are a DevOps specialist..."

WORKER_REGISTRY["devops"] = DevOpsWorker()
```

添加后：
- Planner 的系统提示词自动包含新 Worker
- YAML 模板可使用 `worker: devops`
- LLM 动态规划可分配步骤给 `devops`

### 13.2 自定义 Synthesizer

当前 Synthesizer 简单拼接结果。可以替换为 LLM 驱动的智能综合：

```python
async def _synthesizer_node(self, state: WorkflowState) -> dict:
    # 使用 LLM 智能综合所有结果
    synthesis_messages = [
        {"role": "system", "content": "你是一个综合分析师，请基于以下多个步骤的结果生成一份完整报告。"},
        {"role": "user", "content": formatted_results},
    ]
    response = await llm_service.call(synthesis_messages)
    return {"final_output": response.content, "messages": [AIMessage(content=response.content)]}
```

---

## 14. 与其他模式对比

| 特性 | Single Agent | Multi Agent | Workflow |
|------|-----------|----------|---------|
| **任务分解** | ❌ | Supervisor 路由 | Planner 多步骤规划 |
| **并行执行** | ❌ | ❌（一个 Worker） | ✅ Send API |
| **依赖管理** | ❌ | ❌ | ✅ depends_on |
| **结果综合** | ❌ | ❌ | ✅ Synthesizer |
| **模板系统** | ❌ | ❌ | ✅ YAML 模板 |
| **适用场景** | 简单对话 | 专家路由 | **复杂多步骤任务** |
| **延迟** | 低 | 中（2 次 LLM） | 高（规划 + N 轮执行 + 综合） |
| **LLM 调用次数** | 1-N（工具） | 2-N（路由+处理） | 1(规划) + N(Worker) |

---

### 相关文档

- [返回功能总览 — NEW_FEATURES_GUIDE.md](./NEW_FEATURES_GUIDE.md#4-agent-模式总览)
- [Single Agent 模式](./AGENT_MODE_2_V1_SINGLE.md)
- [Multi-Agent 模式](./AGENT_MODE_3_V1_MULTI.md)

---

> **文档版本**: 1.0
> **对应源文件**: `app/core/langgraph/workflow/graph.py` · `app/core/langgraph/workflow/planner.py` · `app/core/langgraph/workflow/schema.py` · `app/api/v1/chatbot_workflow.py`
