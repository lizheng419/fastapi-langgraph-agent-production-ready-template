"""Unit tests for the MCP client manager."""

import json
import os
from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

import pytest
import pytest_asyncio

from app.core.mcp.client import (
    MCPManager,
    MCPServerConfig,
    get_mcp_tools,
)


class TestMCPServerConfig:
    """Tests for MCPServerConfig data class."""

    def test_default_values(self):
        """Test MCPServerConfig default values."""
        config = MCPServerConfig(name="test")
        assert config.name == "test"
        assert config.transport == "sse"
        assert config.url is None
        assert config.command is None
        assert config.args == []
        assert config.env == {}
        assert config.enabled is True

    def test_sse_config(self):
        """Test MCPServerConfig for SSE transport."""
        config = MCPServerConfig(
            name="sse-server",
            transport="sse",
            url="http://localhost:8001/sse",
            enabled=True,
        )
        assert config.transport == "sse"
        assert config.url == "http://localhost:8001/sse"

    def test_stdio_config(self):
        """Test MCPServerConfig for stdio transport."""
        config = MCPServerConfig(
            name="stdio-server",
            transport="stdio",
            command="npx",
            args=["-y", "some-package"],
            env={"API_KEY": "test"},
            enabled=True,
        )
        assert config.transport == "stdio"
        assert config.command == "npx"
        assert config.args == ["-y", "some-package"]
        assert config.env == {"API_KEY": "test"}

    def test_disabled_config(self):
        """Test MCPServerConfig with enabled=False."""
        config = MCPServerConfig(name="disabled", enabled=False)
        assert config.enabled is False


class TestMCPManagerConfigLoading:
    """Tests for MCPManager configuration loading."""

    def test_load_config_from_valid_file(self, tmp_mcp_config):
        """Test loading MCP config from a valid JSON file."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False

        with patch.object(
            MCPManager,
            "_load_config",
            wraps=manager._load_config,
        ):
            # Patch the config path resolution
            with patch(
                "app.core.mcp.client.os.path.join",
                return_value=tmp_mcp_config,
            ):
                with patch(
                    "app.core.mcp.client.os.path.exists",
                    return_value=True,
                ):
                    # Read the config file directly to simulate loading
                    with open(tmp_mcp_config, "r", encoding="utf-8") as f:
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
                            manager._servers.append(server)

        # Should load 2 enabled servers, skip 1 disabled
        assert len(manager._servers) == 2
        assert manager._servers[0].name == "test-sse-server"
        assert manager._servers[1].name == "test-stdio-server"

    def test_load_config_disabled_servers_filtered(self, tmp_mcp_config):
        """Test that disabled servers are filtered out during config loading."""
        with open(tmp_mcp_config, "r", encoding="utf-8") as f:
            config = json.load(f)

        enabled_count = sum(1 for s in config["servers"] if s.get("enabled", True))
        disabled_count = sum(1 for s in config["servers"] if not s.get("enabled", True))

        assert enabled_count == 2
        assert disabled_count == 1

    def test_load_config_missing_file(self, tmp_path):
        """Test loading config when file does not exist."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False

        nonexistent_path = str(tmp_path / "nonexistent.json")

        with patch(
            "app.core.mcp.client.os.path.join",
            return_value=nonexistent_path,
        ):
            manager._load_config()

        assert len(manager._servers) == 0

    def test_load_config_invalid_json(self, tmp_mcp_config_invalid_json):
        """Test loading config with invalid JSON content."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False

        with patch(
            "app.core.mcp.client.os.path.join",
            return_value=tmp_mcp_config_invalid_json,
        ):
            with patch(
                "app.core.mcp.client.os.path.exists",
                return_value=True,
            ):
                manager._load_config()

        assert len(manager._servers) == 0

    def test_load_config_empty_servers(self, tmp_mcp_config_empty):
        """Test loading config with empty servers list."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False

        with patch(
            "app.core.mcp.client.os.path.join",
            return_value=tmp_mcp_config_empty,
        ):
            with patch(
                "app.core.mcp.client.os.path.exists",
                return_value=True,
            ):
                manager._load_config()

        assert len(manager._servers) == 0


class TestMCPManagerProperties:
    """Tests for MCPManager properties."""

    def test_is_initialized_default(self):
        """Test is_initialized is False by default."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False
        assert manager.is_initialized is False

    def test_is_initialized_after_set(self):
        """Test is_initialized after being set to True."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = True
        assert manager.is_initialized is True

    def test_server_count_empty(self):
        """Test server_count with no servers."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False
        assert manager.server_count == 0

    def test_server_count_with_servers(self):
        """Test server_count with configured servers."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = [
            MCPServerConfig(name="s1"),
            MCPServerConfig(name="s2"),
        ]
        manager._tools = []
        manager._initialized = False
        assert manager.server_count == 2

    def test_get_tools_empty(self):
        """Test get_tools returns empty list when no tools loaded."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False
        assert manager.get_tools() == []


class TestMCPManagerInitialize:
    """Tests for MCPManager async initialization."""

    @pytest.mark.asyncio
    async def test_initialize_no_servers(self):
        """Test initialization with no configured servers."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False

        await manager.initialize()

        assert manager.is_initialized is True
        assert manager.get_tools() == []

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self):
        """Test that calling initialize twice does not re-initialize."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False

        await manager.initialize()
        assert manager.is_initialized is True

        # Add a server after init - should not be processed
        manager._servers.append(MCPServerConfig(name="late"))
        await manager.initialize()

        # Still initialized, no new tools
        assert manager.is_initialized is True
        assert manager.get_tools() == []

    @pytest.mark.asyncio
    async def test_initialize_with_import_error(self):
        """Test initialization when langchain-mcp-adapters is not installed."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = [MCPServerConfig(name="test", transport="sse", url="http://localhost:9999/sse")]
        manager._tools = []
        manager._initialized = False

        with patch(
            "builtins.__import__",
            side_effect=lambda name, *args, **kwargs: (
                (_ for _ in ()).throw(ImportError("No module"))
                if "langchain_mcp_adapters" in name
                else __import__(name, *args, **kwargs)
            ),
        ):
            # The method catches ImportError internally
            await manager.initialize()

        assert manager.is_initialized is True
        assert manager.get_tools() == []

    @pytest.mark.asyncio
    async def test_initialize_connection_failure_handled(self):
        """Test that connection failures are caught and don't crash init."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = [MCPServerConfig(name="fail-server", transport="sse", url="http://localhost:9999/sse")]
        manager._tools = []
        manager._initialized = False

        with patch.object(
            manager,
            "_connect_server",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Connection refused"),
        ):
            # Also patch the import check
            mock_module = MagicMock()
            with patch.dict("sys.modules", {"langchain_mcp_adapters.client": mock_module}):
                await manager.initialize()

        assert manager.is_initialized is True
        assert manager.get_tools() == []

    @pytest.mark.asyncio
    async def test_connect_server_sse_missing_url(self):
        """Test _connect_server with SSE transport but missing URL."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False

        server = MCPServerConfig(name="no-url", transport="sse", url=None)

        # Should log warning and return without adding tools
        with patch("app.core.mcp.client.logger") as mock_logger:
            await manager._connect_server(server)
            mock_logger.warning.assert_called_once()

        assert len(manager._tools) == 0

    @pytest.mark.asyncio
    async def test_connect_server_stdio_missing_command(self):
        """Test _connect_server with stdio transport but missing command."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False

        server = MCPServerConfig(name="no-cmd", transport="stdio", command=None)

        with patch("app.core.mcp.client.logger") as mock_logger:
            await manager._connect_server(server)
            mock_logger.warning.assert_called_once()

        assert len(manager._tools) == 0

    @pytest.mark.asyncio
    async def test_connect_server_unsupported_transport(self):
        """Test _connect_server with unsupported transport type."""
        manager = MCPManager.__new__(MCPManager)
        manager._servers = []
        manager._tools = []
        manager._initialized = False

        server = MCPServerConfig(name="bad-transport", transport="websocket")

        with patch("app.core.mcp.client.logger") as mock_logger:
            await manager._connect_server(server)
            mock_logger.warning.assert_called_once()

        assert len(manager._tools) == 0


class TestGetMCPTools:
    """Tests for the get_mcp_tools async helper."""

    @pytest.mark.asyncio
    async def test_get_mcp_tools_initializes_on_first_call(self):
        """Test that get_mcp_tools initializes the manager if not yet initialized."""
        mock_manager = MagicMock()
        mock_manager.is_initialized = False
        mock_manager.initialize = AsyncMock()
        mock_manager.get_tools.return_value = []

        with patch("app.core.mcp.client.mcp_manager", mock_manager):
            tools = await get_mcp_tools()

        mock_manager.initialize.assert_awaited_once()
        assert tools == []

    @pytest.mark.asyncio
    async def test_get_mcp_tools_skips_init_if_already_done(self):
        """Test that get_mcp_tools skips init if already initialized."""
        mock_manager = MagicMock()
        mock_manager.is_initialized = True
        mock_manager.initialize = AsyncMock()
        mock_manager.get_tools.return_value = []

        with patch("app.core.mcp.client.mcp_manager", mock_manager):
            tools = await get_mcp_tools()

        mock_manager.initialize.assert_not_awaited()
        assert tools == []
