"""MCP client manager for connecting to external MCP servers.

This module provides an async MCP client manager that connects to
configured MCP servers (SSE, streamable_http, or stdio) via
``MultiServerMCPClient`` from ``langchain-mcp-adapters`` and converts
their tools into LangChain-compatible tools for use with LangGraph.

The ``MultiServerMCPClient`` instance is kept alive so that MCP sessions
remain open and tools can communicate with the remote servers at
invocation time.
"""

import json
import os
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from langchain_core.tools.base import BaseTool

from app.core.logging import logger

# Supported transport types (mapped to MultiServerMCPClient keys)
_VALID_TRANSPORTS = {"stdio", "sse", "streamable_http"}


class MCPManager:
    """Manages MCP server connections and tool loading.

    Uses ``MultiServerMCPClient`` to maintain persistent sessions to all
    configured MCP servers.  Tools loaded from these sessions remain
    functional for the lifetime of the manager.
    """

    def __init__(self):
        """Initialize the MCP manager."""
        self._client: Any = None  # MultiServerMCPClient instance (kept alive)
        self._tools: List[BaseTool] = []
        self._initialized = False
        self._server_configs: List[Dict[str, Any]] = []
        self._load_config()

    # ─── Config loading ──────────────────────────────────────────

    def _load_config(self) -> None:
        """Load MCP server configurations from ``mcp_servers.json``."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "mcp_servers.json",
        )

        if not os.path.exists(config_path):
            logger.info("mcp_config_not_found", config_path=config_path)
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            for entry in config.get("servers", []):
                if not entry.get("enabled", True):
                    continue
                self._server_configs.append(entry)
                logger.info(
                    "mcp_server_config_loaded",
                    server_name=entry.get("name", "unknown"),
                    transport=entry.get("transport", "stdio"),
                )

        except Exception:
            logger.exception("mcp_config_load_failed", config_path=config_path)

    # ─── Config conversion ───────────────────────────────────────

    @staticmethod
    def _build_client_dict(configs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Convert ``mcp_servers.json`` entries into the dict format expected by ``MultiServerMCPClient``.

        Returns:
            Dict keyed by server name, values are connection kwargs.
        """
        result: Dict[str, Dict[str, Any]] = {}
        for entry in configs:
            name = entry.get("name", "unknown")
            transport = entry.get("transport", "stdio")

            if transport not in _VALID_TRANSPORTS:
                logger.warning(
                    "mcp_unsupported_transport",
                    server_name=name,
                    transport=transport,
                )
                continue

            server_dict: Dict[str, Any] = {"transport": transport}

            if transport in ("sse", "streamable_http"):
                url = entry.get("url")
                if not url:
                    logger.warning("mcp_server_missing_url", server_name=name)
                    continue
                server_dict["url"] = url
                if entry.get("headers"):
                    server_dict["headers"] = entry["headers"]

            elif transport == "stdio":
                command = entry.get("command")
                if not command:
                    logger.warning("mcp_server_missing_command", server_name=name)
                    continue
                server_dict["command"] = command
                server_dict["args"] = entry.get("args", [])
                env = entry.get("env", {})
                if env:
                    server_dict["env"] = {**os.environ, **env}

            result[name] = server_dict

        return result

    # ─── Initialization ──────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize connections to all configured MCP servers and load tools.

        Uses ``MultiServerMCPClient`` which manages session lifecycle
        internally — sessions stay open so that loaded tools can
        actually invoke the remote MCP servers.
        """
        if self._initialized:
            return

        if not self._server_configs:
            logger.info("no_mcp_servers_configured")
            self._initialized = True
            return

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient
        except ImportError:
            logger.warning(
                "langchain_mcp_adapters_not_installed",
                message="Install with: pip install langchain-mcp-adapters",
            )
            self._initialized = True
            return

        client_dict = self._build_client_dict(self._server_configs)
        if not client_dict:
            logger.warning("mcp_no_valid_servers_after_config_conversion")
            self._initialized = True
            return

        try:
            self._client = MultiServerMCPClient(client_dict)
            self._tools = await self._client.get_tools()
            logger.info(
                "mcp_initialization_complete",
                total_tools=len(self._tools),
                servers=list(client_dict.keys()),
                tool_names=[t.name for t in self._tools],
            )
        except Exception:
            logger.exception("mcp_initialization_failed")
            self._tools = []

        self._initialized = True

    # ─── Cleanup ─────────────────────────────────────────────────

    async def close(self) -> None:
        """Close all MCP server connections gracefully."""
        if self._client is not None:
            try:
                if hasattr(self._client, "close"):
                    await self._client.close()
            except Exception:
                logger.exception("mcp_close_failed")
            self._client = None
            self._tools = []
            self._initialized = False
            logger.info("mcp_connections_closed")

    # ─── Accessors ───────────────────────────────────────────────

    def get_tools(self) -> List[BaseTool]:
        """Get all loaded MCP tools.

        Returns:
            List[BaseTool]: LangChain-compatible tools from MCP servers.
        """
        return self._tools

    @property
    def is_initialized(self) -> bool:
        """Check if MCP manager has been initialized."""
        return self._initialized

    @property
    def server_count(self) -> int:
        """Get the number of configured MCP servers."""
        return len(self._server_configs)


# Global MCP manager instance
mcp_manager = MCPManager()


async def get_mcp_tools() -> List[BaseTool]:
    """Get MCP tools, initializing if needed.

    Returns:
        List[BaseTool]: All available MCP tools.
    """
    if not mcp_manager.is_initialized:
        await mcp_manager.initialize()
    return mcp_manager.get_tools()
