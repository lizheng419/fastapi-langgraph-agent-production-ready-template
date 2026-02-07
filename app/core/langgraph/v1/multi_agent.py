"""Multi-Agent using LangChain v1 create_agent + Supervisor pattern.

Features:
    - Each worker is a create_agent instance with its own middleware
    - Supervisor uses create_agent with handoff tools for worker delegation
    - HITL handled by HumanInTheLoopMiddleware on each worker
    - Built-in streaming, checkpointing, and structured output
"""

import asyncio
from dataclasses import dataclass
from typing import (
    AsyncGenerator,
    Dict,
    List,
    Optional,
)

from langchain.agents import create_agent
from langchain_core.messages import convert_to_openai_messages
from langchain_core.tools import tool
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
from langgraph.graph import (
    END,
    START,
    MessagesState,
    StateGraph,
)
from langgraph.graph.state import (
    Command,
    CompiledStateGraph,
)
from langgraph.types import (
    RunnableConfig,
    StateSnapshot,
)

from app.core.config import settings
from app.core.langgraph.agents.workers import get_worker_configs
from app.core.langgraph.base import BaseAgentMixin
from app.core.langgraph.tools import tools as base_tools
from app.core.langgraph.v1.middleware import (
    AgentContext,
    HITLApprovalMiddleware,
    LangfuseTracingMiddleware,
    MetricsMiddleware,
    skills_aware_prompt,
)
from app.core.logging import logger
from app.schemas import Message
from app.services.llm import LLMRegistry

# ─── V1MultiAgent ──────────────────────────────────────────────────


@dataclass
class V1MultiAgentConfig:
    """Configuration for V1MultiAgent."""

    model: str = settings.DEFAULT_LLM_MODEL
    enable_hitl: bool = True
    enable_tracing: bool = True
    enable_metrics: bool = True
    enable_memory: bool = True
    sensitive_patterns: Optional[List[str]] = None
    worker_configs: Optional[Dict[str, dict]] = None


class V1MultiAgent(BaseAgentMixin):
    """Multi-Agent system using LangChain v1 create_agent with Supervisor pattern.

    Architecture:
        User → Supervisor Agent → [Worker Agent] → Response
                    ↓                    ↓
              route decision      specialist processing
                    ↓                    ↓
              handoff tool        middleware (HITL, tracing, etc.)

    Each worker is an independent create_agent with its own middleware stack.
    The supervisor uses handoff tools to delegate to workers.
    """

    def __init__(self, config: Optional[V1MultiAgentConfig] = None):
        """Initialize V1 Multi-Agent system."""
        self._config = config or V1MultiAgentConfig()
        self._worker_configs = self._config.worker_configs or get_worker_configs()
        self._graph: Optional[CompiledStateGraph] = None
        self._all_tools: List = list(base_tools)
        self._connection_pool = None
        self._memory = None
        self._mcp_initialized = False

        logger.info(
            "v1_multi_agent_initialized",
            model=self._config.model,
            workers=list(self._worker_configs.keys()),
        )

    def _build_worker_middleware(self) -> list:
        """Build middleware stack for worker agents.

        Workers get tracing + metrics + HITL but NOT the dynamic prompt
        (they have their own system_prompt) or summarization/tool filter.
        """
        middlewares = []

        if self._config.enable_tracing:
            middlewares.append(LangfuseTracingMiddleware())

        if self._config.enable_metrics:
            middlewares.append(MetricsMiddleware())

        if self._config.enable_hitl:
            middlewares.append(HITLApprovalMiddleware(sensitive_patterns=self._config.sensitive_patterns))

        return middlewares

    def _create_worker_agents(self) -> Dict[str, object]:
        """Create worker agents using create_agent."""
        workers = {}
        worker_middleware = self._build_worker_middleware()

        model_instance = LLMRegistry.get(self._config.model)
        for name, cfg in self._worker_configs.items():
            workers[name] = create_agent(
                model=model_instance,
                tools=self._all_tools,
                system_prompt=cfg["system_prompt"],
                middleware=worker_middleware,
                name=f"{name}_worker",
            )

        logger.info("v1_worker_agents_created", workers=list(workers.keys()))
        return workers

    async def _build_graph(self) -> CompiledStateGraph:
        """Build the multi-agent graph with supervisor routing.

        Graph structure:
            START → supervisor → [worker_name] → END
                              → general_chat  → END

        The supervisor uses an LLM call to route, then the selected
        worker agent processes the request independently.
        """
        await self._initialize_mcp_tools()

        workers = self._create_worker_agents()

        # Build supervisor system prompt with worker descriptions
        worker_descriptions = "\n".join(
            f"- **{name}**: {cfg['description']}" for name, cfg in self._worker_configs.items()
        )

        supervisor_prompt = (
            "You are a Supervisor agent. Your job is to analyze the user's request "
            "and route it to the most appropriate specialist worker.\n\n"
            f"## Available Workers\n{worker_descriptions}\n\n"
            "## Instructions\n"
            "1. Analyze the user's request carefully.\n"
            "2. If the request matches a worker's specialty, delegate to that worker "
            "by calling the corresponding transfer tool (e.g., transfer_to_researcher).\n"
            "3. If it's a general conversation, respond directly without delegating.\n"
            "4. Always provide a brief reasoning for your routing decision."
        )

        # Create handoff tools for each worker
        handoff_tools = []
        for worker_name in workers:

            @tool(f"transfer_to_{worker_name}")
            def _make_handoff(request: str, _name=worker_name) -> str:
                """Transfer the request to a specialist worker."""
                return f"Transferring to {_name}: {request}"

            _make_handoff.__doc__ = f"Transfer to {worker_name} specialist. Use when the request involves: {self._worker_configs[worker_name]['description']}"
            handoff_tools.append(_make_handoff)

        # Create supervisor agent
        supervisor_model = LLMRegistry.get(self._config.model)
        supervisor = create_agent(
            model=supervisor_model,
            tools=handoff_tools,
            system_prompt=supervisor_prompt,
            middleware=[LangfuseTracingMiddleware(), MetricsMiddleware()] if self._config.enable_tracing else [],
            name="supervisor",
        )

        # Build the graph
        class MultiAgentState(MessagesState):
            """State for the multi-agent graph."""

            pass

        builder = StateGraph(MultiAgentState)

        # Supervisor node
        async def supervisor_node(state: MultiAgentState, config: dict = None) -> Command:
            response = await supervisor.ainvoke(state, config=config)

            # Scan ALL messages for handoff tool calls
            # (supervisor agent executes tools internally, so last_msg may not have tool_calls)
            for msg in response["messages"]:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc.get("name", "")
                        for worker_name in workers:
                            if tool_name == f"transfer_to_{worker_name}":
                                logger.info(
                                    "v1_supervisor_routed",
                                    worker=worker_name,
                                    tool_name=tool_name,
                                )
                                return Command(
                                    update={"messages": state["messages"]},
                                    goto=worker_name,
                                )

            # No handoff — supervisor responded directly
            return Command(update={"messages": response["messages"]}, goto=END)

        builder.add_node("supervisor", supervisor_node)

        # Worker nodes
        for worker_name, worker_agent in workers.items():

            async def worker_node(
                state: MultiAgentState, config: dict = None, _agent=worker_agent, _name=worker_name
            ) -> Command:
                try:
                    response = await _agent.ainvoke(state, config=config)
                    logger.info("v1_worker_completed", worker=_name)
                    return Command(update={"messages": response["messages"]}, goto=END)
                except Exception as e:
                    logger.exception("v1_worker_failed", worker=_name, error=str(e))
                    from langchain_core.messages import AIMessage

                    return Command(
                        update={
                            "messages": [
                                AIMessage(content=f"The {_name} specialist encountered an error. Please try again.")
                            ]
                        },
                        goto=END,
                    )

            builder.add_node(worker_name, worker_node)

        # Edges
        builder.add_edge(START, "supervisor")

        # Checkpointer
        checkpointer = await self._setup_checkpointer()

        graph = builder.compile(
            checkpointer=checkpointer,
            name=f"{settings.PROJECT_NAME} V1 Multi-Agent ({settings.ENVIRONMENT.value})",
        )

        logger.info(
            "v1_multi_agent_graph_created",
            workers=list(workers.keys()),
            has_checkpointer=checkpointer is not None,
        )

        return graph

    async def get_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
    ) -> list[Message]:
        """Get a response from the V1 multi-agent system.

        Args:
            messages: User messages.
            session_id: Session ID for checkpointing.
            user_id: User ID for memory and tracing.

        Returns:
            List of response messages.
        """
        if self._graph is None:
            self._graph = await self._build_graph()

        relevant_memory = ""
        if user_id and self._config.enable_memory:
            relevant_memory = (
                await self._get_relevant_memory(user_id, messages[-1].content)
            ) or "No relevant memory found."

        input_messages = [{"role": m.role, "content": m.content} for m in messages]

        # Prepend memory context as a system-level hint
        if relevant_memory:
            memory_msg = {
                "role": "system",
                "content": f"Relevant memory from previous conversations:\n{relevant_memory}",
            }
            input_messages = [memory_msg] + input_messages

        config = {
            "configurable": {"thread_id": session_id},
            "metadata": {
                "user_id": user_id,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
            },
        }

        try:
            response = await self._graph.ainvoke(
                {"messages": input_messages},
                config=config,
            )

            if user_id:
                asyncio.create_task(
                    self._update_long_term_memory(
                        user_id,
                        convert_to_openai_messages(response["messages"]),
                        config["metadata"],
                    )
                )

            return self._process_messages(response["messages"])
        except Exception as e:
            logger.exception("v1_multi_agent_response_failed", error=str(e))
            return []

    async def get_stream_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response from the V1 multi-agent system.

        Args:
            messages: User messages.
            session_id: Session ID.
            user_id: User ID.

        Yields:
            Response content tokens.
        """
        if self._graph is None:
            self._graph = await self._build_graph()

        relevant_memory = ""
        if user_id and self._config.enable_memory:
            relevant_memory = (
                await self._get_relevant_memory(user_id, messages[-1].content)
            ) or "No relevant memory found."

        input_messages = [{"role": m.role, "content": m.content} for m in messages]
        if relevant_memory:
            memory_msg = {
                "role": "system",
                "content": f"Relevant memory from previous conversations:\n{relevant_memory}",
            }
            input_messages = [memory_msg] + input_messages

        config = {
            "configurable": {"thread_id": session_id},
            "callbacks": [LangfuseCallbackHandler()],
            "metadata": {
                "langfuse_user_id": user_id,
                "langfuse_session_id": session_id,
                "user_id": user_id,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
            },
        }

        try:
            async for token, _ in self._graph.astream(
                {"messages": input_messages},
                config=config,
                stream_mode="messages",
            ):
                try:
                    yield token.content
                except Exception:
                    continue

            if user_id:
                state: StateSnapshot = await self._graph.aget_state(config=config)
                if state.values and "messages" in state.values:
                    asyncio.create_task(
                        self._update_long_term_memory(
                            user_id,
                            convert_to_openai_messages(state.values["messages"]),
                            config["metadata"],
                        )
                    )
        except Exception as e:
            logger.exception("v1_multi_stream_failed", error=str(e))
            raise
