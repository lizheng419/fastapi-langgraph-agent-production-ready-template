"""MCP (Model Context Protocol) integration for the LangGraph Agent.

This package provides MCP client configuration and tool loading,
enabling the agent to connect to external MCP servers and use
their tools dynamically.
"""

from app.core.mcp.client import (
    get_mcp_tools,
    mcp_manager,
)

__all__ = ["get_mcp_tools", "mcp_manager"]
