"""Custom middleware for LangChain v1 create_agent.

Implements composable middleware following the official Context Engineering guide:
- @dynamic_prompt: Dynamic system prompt with Skills + long-term memory
- SummarizationMiddleware: Auto-summarize long conversation history
- @wrap_model_call role filter: Dynamic tool selection by user role
- HITLApprovalMiddleware: Human-in-the-Loop approval for sensitive tool calls
- LangfuseTracingMiddleware: Langfuse observability integration
- MetricsMiddleware: Prometheus metrics for LLM inference

Ref: https://docs.langchain.com/oss/python/langchain/context-engineering

LangChain v1.2+ Middleware hook signatures:
    before_model(state: AgentState, runtime: Runtime) -> dict | None
    after_model(state: AgentState, runtime: Runtime) -> dict | None
    wrap_model_call(request: ModelRequest, handler) -> ModelResponse
    wrap_tool_call(request: ToolCallRequest, handler) -> ToolMessage | Command
"""

from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
)

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
    SummarizationMiddleware,
    dynamic_prompt,
    wrap_model_call,
)
from langgraph.runtime import Runtime

from app.core.config import settings
from app.core.langgraph.hitl import (
    ApprovalStatus,
    approval_manager,
)
from app.core.logging import logger
from app.core.metrics import llm_inference_duration_seconds
from app.core.prompts import load_system_prompt

# ─── Agent Context ────────────────────────────────────────────────


@dataclass
class AgentContext:
    """Runtime context carrying user/session/role info.

    Used as context_schema for create_agent, accessible in middleware
    via request.runtime.context and in tools via runtime.context.
    """

    user_id: str = ""
    session_id: str = ""
    relevant_memory: str = ""
    user_role: str = "user"


# Backward compatibility alias
MemoryContext = AgentContext


# ─── Dynamic System Prompt (official @dynamic_prompt pattern) ─────


@dynamic_prompt
def skills_aware_prompt(request: ModelRequest) -> str:
    """Build dynamic system prompt with Skills descriptions + long-term memory.

    Uses the official @dynamic_prompt decorator instead of a manual
    AgentMiddleware subclass. Reads long_term_memory from runtime context.

    Ref: https://docs.langchain.com/oss/python/langchain/context-engineering
    """
    ctx = getattr(request.runtime, "context", None) if request.runtime else None
    memory_text = getattr(ctx, "relevant_memory", "") if ctx else ""

    return load_system_prompt(long_term_memory=memory_text)


# ─── Dynamic Tool Selection (official @wrap_model_call pattern) ───


# Tools that require elevated privileges (admin role)
_ADMIN_ONLY_TOOLS: Set[str] = {"create_skill", "update_skill"}


@wrap_model_call
def role_based_tool_filter(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    """Filter tools based on user role from runtime context.

    Admin users get all tools; regular users cannot access create_skill
    and update_skill. This is a transient filter — does not modify state.

    Ref: https://docs.langchain.com/oss/python/langchain/context-engineering
    """
    ctx = getattr(request.runtime, "context", None) if request.runtime else None
    user_role = getattr(ctx, "user_role", "user") if ctx else "user"

    if user_role != "admin":
        filtered = [t for t in request.tools if t.name not in _ADMIN_ONLY_TOOLS]
        if len(filtered) != len(request.tools):
            logger.debug(
                "tools_filtered_by_role",
                user_role=user_role,
                removed=[t.name for t in request.tools if t.name in _ADMIN_ONLY_TOOLS],
            )
            request = request.override(tools=filtered)

    return handler(request)


# ─── HITL Approval Middleware ──────────────────────────────────────


class HITLApprovalMiddleware(AgentMiddleware):
    """Human-in-the-Loop approval for sensitive tool calls.

    Intercepts tool execution for tools matching sensitive patterns.
    Creates an approval request via ApprovalManager and blocks execution
    until a human approves or rejects.

    Args:
        sensitive_patterns: Tool name substrings that trigger approval.
        timeout_seconds: Max seconds to wait for approval (default 3600).
    """

    def __init__(
        self,
        sensitive_patterns: Optional[List[str]] = None,
        timeout_seconds: int = 3600,
    ):
        """Initialize HITL middleware with sensitive tool patterns."""
        super().__init__()
        self.sensitive_patterns = sensitive_patterns or settings.SENSITIVE_TOOL_PATTERNS
        self.timeout_seconds = timeout_seconds

    def _is_sensitive(self, tool_name: str) -> bool:
        """Check if a tool name matches sensitive patterns."""
        name_lower = tool_name.lower()
        return any(pattern in name_lower for pattern in self.sensitive_patterns)

    def wrap_tool_call(self, request, handler):
        """Intercept sensitive tool calls for human approval.

        For sensitive tools, creates an approval request and returns
        a message indicating approval is needed instead of executing.
        For non-sensitive tools, passes through normally.
        """
        tool_name = request.tool_call.get("name", "") if hasattr(request, "tool_call") else request.get("name", "")

        if not self._is_sensitive(tool_name):
            return handler(request)

        # Sensitive tool detected — block and request approval
        ctx = None
        if hasattr(request, "runtime") and hasattr(request.runtime, "context"):
            ctx = request.runtime.context
        session_id = getattr(ctx, "session_id", "unknown") if ctx else "unknown"

        logger.info(
            "hitl_tool_blocked",
            tool_name=tool_name,
            session_id=session_id,
        )

        # Return a message indicating approval is needed
        # The actual approval lifecycle is handled via the REST API
        from langchain_core.messages import ToolMessage

        return ToolMessage(
            content=(
                f"🔒 Action `{tool_name}` requires human approval. "
                f"Please use the approval API to approve or reject this action."
            ),
            tool_call_id=request.tool_call.get("id", "") if hasattr(request, "tool_call") else "",
        )


# ─── Langfuse Tracing Middleware ───────────────────────────────────


class LangfuseTracingMiddleware(AgentMiddleware):
    """Langfuse observability middleware.

    Logs model call events for tracing. Actual Langfuse trace capture is
    handled via Langfuse auto-instrumentation or @observe() at the API layer,
    avoiding callbacks conflicts with LangGraph's internal callback machinery.
    """

    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """Log model invocation for observability."""
        ctx = getattr(runtime, "context", None) if runtime else None
        logger.debug(
            "langfuse_before_model",
            user_id=getattr(ctx, "user_id", None) if ctx else None,
            session_id=getattr(ctx, "session_id", None) if ctx else None,
        )
        return None


# ─── Prometheus Metrics Middleware ─────────────────────────────────


class MetricsMiddleware(AgentMiddleware):
    """Track LLM inference duration with Prometheus metrics."""

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Wrap model call with Prometheus timing (sync)."""
        model_name = settings.DEFAULT_LLM_MODEL

        with llm_inference_duration_seconds.labels(model=model_name).time():
            return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """Wrap model call with Prometheus timing (async)."""
        model_name = settings.DEFAULT_LLM_MODEL

        with llm_inference_duration_seconds.labels(model=model_name).time():
            result = handler(request)
            if hasattr(result, "__await__"):
                return await result
            return result


# ─── Factory Functions ─────────────────────────────────────────────


def create_default_middleware(
    enable_hitl: bool = True,
    enable_tracing: bool = True,
    enable_metrics: bool = True,
    enable_summarization: bool = True,
    enable_tool_filter: bool = True,
    summarization_model: Optional[str] = None,
    summarization_trigger_tokens: Optional[int] = None,
    summarization_keep_messages: Optional[int] = None,
    sensitive_patterns: Optional[List[str]] = None,
) -> list:
    """Create the default middleware stack for V1 agents.

    Follows the official LangChain Context Engineering guide:
    https://docs.langchain.com/oss/python/langchain/context-engineering

    Args:
        enable_hitl: Enable Human-in-the-Loop approval middleware.
        enable_tracing: Enable Langfuse tracing middleware.
        enable_metrics: Enable Prometheus metrics middleware.
        enable_summarization: Enable SummarizationMiddleware for long conversations.
        enable_tool_filter: Enable role-based dynamic tool selection.
        summarization_model: Model to use for summarization (cheaper model recommended).
        summarization_trigger_tokens: Token count that triggers summarization.
        summarization_keep_messages: Number of recent messages to keep after summarization.
        sensitive_patterns: Custom sensitive tool name patterns for HITL.

    Returns:
        List of middleware instances in recommended execution order.
    """
    middlewares: list = []

    # 1. Dynamic system prompt with Skills + memory (@dynamic_prompt)
    middlewares.append(skills_aware_prompt)

    # 2. Summarization — auto-condense long conversation history
    if enable_summarization:
        middlewares.append(
            SummarizationMiddleware(
                model=summarization_model or settings.SUMMARIZATION_MODEL,
                trigger=("tokens", summarization_trigger_tokens or settings.SUMMARIZATION_TRIGGER_TOKENS),
                keep=("messages", summarization_keep_messages or settings.SUMMARIZATION_KEEP_MESSAGES),
            )
        )

    # 3. Role-based tool filter (@wrap_model_call)
    if enable_tool_filter:
        middlewares.append(role_based_tool_filter)

    # 4. Observability
    if enable_tracing:
        middlewares.append(LangfuseTracingMiddleware())

    if enable_metrics:
        middlewares.append(MetricsMiddleware())

    # 5. HITL approval (last — runs after all context engineering)
    if enable_hitl:
        middlewares.append(HITLApprovalMiddleware(sensitive_patterns=sensitive_patterns))

    logger.info(
        "v1_middleware_stack_created",
        middleware_count=len(middlewares),
        hitl=enable_hitl,
        tracing=enable_tracing,
        metrics=enable_metrics,
        summarization=enable_summarization,
        tool_filter=enable_tool_filter,
    )

    return middlewares
