"""MCP client manager for connecting to external MCP servers.

This module provides an async MCP client manager that connects to
configured MCP servers (SSE or stdio) and converts their tools
into LangChain-compatible tools for use with LangGraph.
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


class MCPServerConfig:
    """Configuration for a single MCP server connection.

    Attributes:
        name: Human-readable name for the server.
        transport: Transport type ('sse' or 'stdio').
        url: URL for SSE transport.
        command: Command for stdio transport.
        args: Arguments for stdio transport command.
        env: Environment variables for stdio transport.
        enabled: Whether this server is enabled.
    """

    def __init__(
        self,
        name: str,
        transport: str = "sse",
        url: Optional[str] = None,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        enabled: bool = True,
    ):
        """Initialize MCP server configuration."""
        self.name = name
        self.transport = transport
        self.url = url
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.enabled = enabled


class MCPManager:
    """Manages MCP server connections and tool loading.

    Handles lifecycle of MCP client sessions and provides
    LangChain-compatible tools from connected MCP servers.
    """

    def __init__(self):
        """Initialize the MCP manager."""
        self._servers: List[MCPServerConfig] = []
        self._tools: List[BaseTool] = []
        self._initialized = False
        self._load_config()

    def _load_config(self) -> None:
        """Load MCP server configurations from environment or config file."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "mcp_servers.json",
        )

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

                for server_config in config.get("servers", []):
                    server = MCPServerConfig(
                        name=server_config.get("name", "unknown"),
                        transport=server_config.get("transport", "sse"),
                        url=server_config.get("url"),
                        command=server_config.get("command"),
                        args=server_config.get("args", []),
                        env=server_config.get("env", {}),
                        enabled=server_config.get("enabled", True),
                    )
                    if server.enabled:
                        self._servers.append(server)
                        logger.info("mcp_server_config_loaded", server_name=server.name, transport=server.transport)

            except Exception as e:
                logger.exception("mcp_config_load_failed", error=str(e), config_path=config_path)
        else:
            logger.info("mcp_config_not_found", config_path=config_path)

    async def initialize(self) -> None:
        """Initialize connections to all configured MCP servers and load tools.

        This method connects to each configured MCP server using
        langchain-mcp-adapters and converts their tools to LangChain format.
        """
        if self._initialized:
            return

        if not self._servers:
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

        for server in self._servers:
            try:
                await self._connect_server(server)
            except Exception as e:
                logger.exception(
                    "mcp_server_connection_failed",
                    server_name=server.name,
                    error=str(e),
                )

        self._initialized = True
        logger.info("mcp_initialization_complete", total_tools=len(self._tools))

    async def _connect_server(self, server: MCPServerConfig) -> None:
        """Connect to a single MCP server and load its tools.

        Args:
            server: The server configuration to connect to.
        """
        from langchain_mcp_adapters.tools import load_mcp_tools
        from mcp import ClientSession

        if server.transport == "sse":
            if not server.url:
                logger.warning("mcp_server_missing_url", server_name=server.name)
                return

            from mcp.client.sse import sse_client

            async with sse_client(url=server.url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                    self._tools.extend(tools)
                    logger.info(
                        "mcp_server_connected",
                        server_name=server.name,
                        transport="sse",
                        tools_count=len(tools),
                        tool_names=[t.name for t in tools],
                    )

        elif server.transport == "stdio":
            if not server.command:
                logger.warning("mcp_server_missing_command", server_name=server.name)
                return

            from mcp.client.stdio import StdioServerParameters, stdio_client

            server_params = StdioServerParameters(
                command=server.command,
                args=server.args,
                env={**os.environ, **server.env} if server.env else None,
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
                    self._tools.extend(tools)
                    logger.info(
                        "mcp_server_connected",
                        server_name=server.name,
                        transport="stdio",
                        tools_count=len(tools),
                        tool_names=[t.name for t in tools],
                    )
        else:
            logger.warning("mcp_unsupported_transport", server_name=server.name, transport=server.transport)

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
        return len(self._servers)


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
