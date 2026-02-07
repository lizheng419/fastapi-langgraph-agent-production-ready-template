"""Shared base mixin for all agent and workflow graph classes.

Provides common infrastructure methods:
- PostgreSQL connection pool management
- Long-term memory (mem0) initialization and operations
- MCP tool loading
- Message format conversion
- Checkpointer setup
- Chat history clearing
"""

from typing import (
    List,
    Optional,
)
from urllib.parse import quote_plus

from langchain_core.messages import (
    BaseMessage,
    convert_to_openai_messages,
)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from mem0 import AsyncMemory
from psycopg_pool import AsyncConnectionPool

from app.core.config import (
    Environment,
    settings,
)
from app.core.logging import logger
from app.core.mcp import get_mcp_tools
from app.schemas import Message


class BaseAgentMixin:
    """Mixin providing shared infrastructure for all agent/graph classes.

    Subclasses must initialize the following attributes in their __init__:
        self._connection_pool: Optional[AsyncConnectionPool] = None
        self._memory: Optional[AsyncMemory] = None
        self._all_tools: List = list(tools)  # if MCP tools are needed
        self._mcp_initialized: bool = False   # if MCP tools are needed
    """

    # ─── Connection Pool ──────────────────────────────────────────

    async def _get_connection_pool(self) -> Optional[AsyncConnectionPool]:
        """Get or create a PostgreSQL connection pool.

        Returns:
            AsyncConnectionPool or None in production if DB unavailable.
        """
        if self._connection_pool is None:
            try:
                self._connection_pool = AsyncConnectionPool(
                    "",
                    open=False,
                    max_size=settings.POSTGRES_POOL_SIZE,
                    kwargs={
                        "host": settings.POSTGRES_HOST,
                        "port": settings.POSTGRES_PORT,
                        "dbname": settings.POSTGRES_DB,
                        "user": settings.POSTGRES_USER,
                        "password": settings.POSTGRES_PASSWORD,
                        "autocommit": True,
                        "connect_timeout": 5,
                        "prepare_threshold": None,
                    },
                )
                await self._connection_pool.open()
                logger.info("connection_pool_created", max_size=settings.POSTGRES_POOL_SIZE)
            except Exception as e:
                logger.exception("connection_pool_creation_failed", error=str(e))
                if settings.ENVIRONMENT == Environment.PRODUCTION:
                    return None
                raise e
        return self._connection_pool

    # ─── Checkpointer ────────────────────────────────────────────

    async def _setup_checkpointer(self) -> Optional[AsyncPostgresSaver]:
        """Create and set up a PostgreSQL checkpointer.

        Returns:
            AsyncPostgresSaver or None if connection pool unavailable.

        Raises:
            Exception: If pool init fails in non-production environments.
        """
        connection_pool = await self._get_connection_pool()
        if connection_pool:
            checkpointer = AsyncPostgresSaver(connection_pool)
            await checkpointer.setup()
            return checkpointer

        if settings.ENVIRONMENT != Environment.PRODUCTION:
            raise Exception("Connection pool initialization failed")
        return None

    # ─── Long-Term Memory ─────────────────────────────────────────

    async def _init_long_term_memory(self) -> Optional[AsyncMemory]:
        """Initialize mem0 long-term memory using pgvector on the main PostgreSQL instance.

        Returns:
            AsyncMemory instance or None on failure.
        """
        if self._memory is None:
            try:
                self._memory = await AsyncMemory.from_config(
                    config_dict={
                        "vector_store": {
                            "provider": "pgvector",
                            "config": {
                                "collection_name": settings.LONG_TERM_MEMORY_COLLECTION_NAME,
                                "embedding_model_dims": settings.LONG_TERM_MEMORY_EMBEDDER_DIMS,
                                "connection_string": (
                                    f"postgresql://{quote_plus(settings.POSTGRES_USER)}:{quote_plus(settings.POSTGRES_PASSWORD)}"
                                    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
                                ),
                            },
                        },
                        "llm": {
                            "provider": "openai",
                            "config": {
                                "model": settings.LONG_TERM_MEMORY_MODEL,
                                **({"openai_base_url": settings.OPENAI_API_BASE} if settings.OPENAI_API_BASE else {}),
                            },
                        },
                        "embedder": {
                            "provider": "openai",
                            "config": {
                                "model": settings.LONG_TERM_MEMORY_EMBEDDER_MODEL,
                                **(
                                    {"openai_base_url": settings.LONG_TERM_MEMORY_EMBEDDER_BASE_URL}
                                    if settings.LONG_TERM_MEMORY_EMBEDDER_BASE_URL
                                    else {}
                                ),
                            },
                        },
                    }
                )
                logger.info("long_term_memory_initialized", collection=settings.LONG_TERM_MEMORY_COLLECTION_NAME)
            except Exception as e:
                logger.exception("long_term_memory_initialization_failed", error=str(e))
                return None
        return self._memory

    async def _get_relevant_memory(self, user_id: str, query: str) -> str:
        """Retrieve relevant long-term memories for the user.

        Args:
            user_id: The user ID.
            query: The query to search for.

        Returns:
            Formatted memory string, or empty string on failure.
        """
        memory = await self._init_long_term_memory()
        if memory is None:
            return ""
        try:
            results = await memory.search(user_id=str(user_id), query=query)
            return "\n".join([f"* {r['memory']}" for r in results["results"]])
        except Exception as e:
            logger.exception("memory_retrieval_failed", error=str(e), user_id=user_id)
            return ""

    async def _update_long_term_memory(self, user_id: str, messages: list, metadata: dict = None) -> None:
        """Update long-term memory in background.

        Args:
            user_id: The user ID.
            messages: Messages to store.
            metadata: Optional metadata to include.
        """
        memory = await self._init_long_term_memory()
        if memory is None:
            return
        try:
            await memory.add(messages, user_id=str(user_id), metadata=metadata)
            logger.info("long_term_memory_updated", user_id=user_id)
        except Exception as e:
            logger.exception("long_term_memory_update_failed", error=str(e), user_id=user_id)

    # ─── MCP Tools ────────────────────────────────────────────────

    async def _initialize_mcp_tools(self) -> None:
        """Load MCP tools asynchronously and add them to the tool list.

        Idempotent — only runs once per instance.
        """
        if self._mcp_initialized:
            return
        try:
            mcp_tools = await get_mcp_tools()
            if mcp_tools:
                self._all_tools.extend(mcp_tools)
                logger.info(
                    "mcp_tools_integrated",
                    mcp_tool_count=len(mcp_tools),
                    total_tool_count=len(self._all_tools),
                )
        except Exception as e:
            logger.exception("mcp_tools_initialization_failed", error=str(e))
        self._mcp_initialized = True

    # ─── Message Processing ───────────────────────────────────────

    def _process_messages(self, messages: list[BaseMessage]) -> list[Message]:
        """Convert LangChain messages to API response format.

        Filters to only assistant and user messages with non-empty content.

        Args:
            messages: LangChain BaseMessage list.

        Returns:
            List of Message schema objects.
        """
        openai_style = convert_to_openai_messages(messages)
        return [
            Message(role=m["role"], content=str(m["content"]))
            for m in openai_style
            if m["role"] in ["assistant", "user"] and m["content"]
        ]

    # ─── Chat History ─────────────────────────────────────────────

    async def _clear_chat_history(self, session_id: str) -> None:
        """Clear all checkpoint data for a given session.

        Args:
            session_id: The session ID to clear history for.

        Raises:
            Exception: If clearing fails.
        """
        try:
            conn_pool = await self._get_connection_pool()
            async with conn_pool.connection() as conn:
                for table in settings.CHECKPOINT_TABLES:
                    try:
                        await conn.execute(f"DELETE FROM {table} WHERE thread_id = %s", (session_id,))
                        logger.info("chat_history_cleared", table=table, session_id=session_id)
                    except Exception as e:
                        logger.exception("clear_history_table_failed", table=table, error=str(e))
                        raise
        except Exception as e:
            logger.exception("clear_chat_history_failed", error=str(e), session_id=session_id)
            raise
