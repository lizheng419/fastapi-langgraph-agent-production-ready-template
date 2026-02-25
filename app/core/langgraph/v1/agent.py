"""Single Agent using LangChain v1 create_agent + Middleware.

Features:
    - langchain.agents.create_agent handles the agent loop
    - Middleware handles prompt, memory, tracing, metrics
    - Built-in checkpointing, streaming, HITL support
    - Cleaner separation of concerns
"""

import asyncio
from dataclasses import dataclass
from typing import (
    AsyncGenerator,
    List,
    Optional,
)

from langchain.agents import create_agent
from langchain_core.messages import convert_to_openai_messages
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
from langgraph.types import StateSnapshot

from app.core.config import settings
from app.core.langgraph.base import BaseAgentMixin
from app.core.langgraph.tools import tools
from app.core.langgraph.v1.middleware import (
    AgentContext,
    create_default_middleware,
)
from app.core.logging import logger
from app.schemas import Message
from app.services.llm import LLMRegistry


@dataclass
class V1AgentConfig:
    """Configuration for V1Agent."""

    model: str = settings.DEFAULT_LLM_MODEL
    enable_hitl: bool = True
    enable_memory: bool = True
    enable_tracing: bool = True
    enable_metrics: bool = True
    enable_summarization: bool = True
    enable_tool_filter: bool = True
    sensitive_patterns: Optional[List[str]] = None


class V1Agent(BaseAgentMixin):
    """Single Agent using LangChain v1 create_agent API.

    Features:
    - create_agent with composable middleware
    - Automatic MCP tool integration
    - Long-term memory via mem0
    - Langfuse tracing
    - Prometheus metrics
    - HITL approval via middleware
    - PostgreSQL checkpointing
    """

    def __init__(self, config: Optional[V1AgentConfig] = None):
        """Initialize V1 Agent."""
        self._config = config or V1AgentConfig()
        self._agent = None
        self._all_tools: List = list(tools)
        self._connection_pool = None
        self._memory = None
        self._mcp_initialized = False

        logger.info(
            "v1_agent_initialized",
            model=self._config.model,
            environment=settings.ENVIRONMENT.value,
        )

    async def _create_agent(self):
        """Build the create_agent instance with middleware and checkpointer."""
        await self._initialize_mcp_tools()

        # Build middleware stack
        middleware = create_default_middleware(
            enable_hitl=self._config.enable_hitl,
            enable_tracing=self._config.enable_tracing,
            enable_metrics=self._config.enable_metrics,
            enable_summarization=self._config.enable_summarization,
            enable_tool_filter=self._config.enable_tool_filter,
            sensitive_patterns=self._config.sensitive_patterns,
        )

        # Setup checkpointer
        checkpointer = await self._setup_checkpointer()

        # Create agent using LangChain v1 API
        model_instance = LLMRegistry.get(self._config.model)
        self._agent = create_agent(
            model=model_instance,
            tools=self._all_tools,
            middleware=middleware,
            checkpointer=checkpointer,
            context_schema=AgentContext,
            name=f"{settings.PROJECT_NAME} V1 Agent ({settings.ENVIRONMENT.value})",
        )

        logger.info(
            "v1_agent_created",
            model=self._config.model,
            tool_count=len(self._all_tools),
            middleware_count=len(middleware),
            has_checkpointer=checkpointer is not None,
        )

        return self._agent

    async def get_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
    ) -> list[Message]:
        """Get a response from the V1 agent.

        Args:
            messages: User messages.
            session_id: Session ID for checkpointing.
            user_id: User ID for memory and tracing.

        Returns:
            List of response messages.
        """
        if self._agent is None:
            await self._create_agent()

        # Prepare memory context — only load long-term memory for
        # continuation messages (len > 1).  First message in a new session
        # starts fresh so users can test without cross-session bleed.
        relevant_memory = ""
        if user_id and self._config.enable_memory and len(messages) > 1:
            relevant_memory = (
                await self._get_relevant_memory(user_id, messages[-1].content)
            ) or "No relevant memory found."

        # Build input messages in OpenAI format
        input_messages = [{"role": m.role, "content": m.content} for m in messages]

        # Build runtime context
        context = AgentContext(
            user_id=user_id or "",
            session_id=session_id,
            relevant_memory=relevant_memory,
        )

        config = {
            "configurable": {"thread_id": session_id},
            "metadata": {
                "user_id": user_id,
                "session_id": session_id,
                "environment": settings.ENVIRONMENT.value,
            },
        }

        try:
            response = await self._agent.ainvoke(
                {"messages": input_messages},
                config=config,
                context=context,
            )

            # Background memory update
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
            logger.exception("v1_agent_response_failed", error=str(e), session_id=session_id)
            return []

    async def get_stream_response(
        self,
        messages: list[Message],
        session_id: str,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens from the V1 agent.

        Args:
            messages: User messages.
            session_id: Session ID for checkpointing.
            user_id: User ID for memory and tracing.

        Yields:
            Response content tokens.
        """
        if self._agent is None:
            await self._create_agent()

        # Only load long-term memory for continuation messages (len > 1)
        relevant_memory = ""
        if user_id and self._config.enable_memory and len(messages) > 1:
            relevant_memory = (
                await self._get_relevant_memory(user_id, messages[-1].content)
            ) or "No relevant memory found."

        input_messages = [{"role": m.role, "content": m.content} for m in messages]

        context = AgentContext(
            user_id=user_id or "",
            session_id=session_id,
            relevant_memory=relevant_memory,
        )

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
            async for token, _ in self._agent.astream(
                {"messages": input_messages},
                config=config,
                context=context,
                stream_mode="messages",
            ):
                try:
                    yield token.content
                except Exception as token_error:
                    logger.exception("v1_stream_token_error", error=str(token_error))
                    continue

            # Background memory update after streaming
            if user_id:
                state: StateSnapshot = await self._agent.aget_state(config=config)
                if state.values and "messages" in state.values:
                    asyncio.create_task(
                        self._update_long_term_memory(
                            user_id,
                            convert_to_openai_messages(state.values["messages"]),
                            config["metadata"],
                        )
                    )
        except Exception as e:
            logger.exception("v1_stream_error", error=str(e), session_id=session_id)
            raise

    async def get_chat_history(self, session_id: str) -> list[Message]:
        """Get chat history for a session."""
        if self._agent is None:
            await self._create_agent()

        state: StateSnapshot = await self._agent.aget_state(config={"configurable": {"thread_id": session_id}})
        return self._process_messages(state.values["messages"]) if state.values else []

    async def clear_chat_history(self, session_id: str) -> None:
        """Clear chat history for a session."""
        await self._clear_chat_history(session_id)
