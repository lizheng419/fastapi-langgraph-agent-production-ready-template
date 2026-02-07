"""Integration tests for Skills + MCP within the LangGraph Agent."""

from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)

import pytest

from app.core.skills.schema import Skill


class TestSkillsInToolsList:
    """Tests verifying Skills integration into the LangGraph tools list."""

    def test_load_skill_in_tools_list(self):
        """Test that load_skill_tool is present in the tools list."""
        from app.core.langgraph.tools import tools

        tool_names = [t.name for t in tools]
        assert "load_skill" in tool_names

    def test_duckduckgo_still_in_tools_list(self):
        """Test that existing tools are still present after Skills integration."""
        from app.core.langgraph.tools import tools

        tool_names = [t.name for t in tools]
        assert "duckduckgo_search" in tool_names

    def test_tools_list_has_expected_count(self):
        """Test the total tool count (duckduckgo_search + load_skill)."""
        from app.core.langgraph.tools import tools

        assert len(tools) >= 2


class TestSkillsInSystemPrompt:
    """Tests verifying Skills descriptions are injected into the system prompt."""

    def test_system_prompt_contains_skills_section(self):
        """Test that the generated system prompt includes the skills section."""
        from app.core.prompts import load_system_prompt

        prompt = load_system_prompt(long_term_memory="No memories yet.")

        assert "Available Skills" in prompt or "load_skill" in prompt

    def test_system_prompt_contains_skill_names(self):
        """Test that built-in skill names appear in the system prompt."""
        from app.core.prompts import load_system_prompt

        prompt = load_system_prompt(long_term_memory="No memories yet.")

        assert "sql_query" in prompt
        assert "data_analysis" in prompt
        assert "code_review" in prompt
        assert "api_design" in prompt

    def test_system_prompt_still_has_base_content(self):
        """Test that the system prompt retains its base content after Skills injection."""
        from app.core.prompts import load_system_prompt

        prompt = load_system_prompt(long_term_memory="Test memory content.")

        assert "Test memory content." in prompt
        assert "Instructions" in prompt

    def test_system_prompt_contains_load_skill_instruction(self):
        """Test that the system prompt instructs the agent to use load_skill."""
        from app.core.prompts import load_system_prompt

        prompt = load_system_prompt(long_term_memory="")

        assert "load_skill" in prompt


class TestSkillsEndToEndFlow:
    """Tests simulating the full skill loading flow."""

    def test_load_builtin_skill_returns_content(self):
        """Test loading a built-in skill returns its full content."""
        from app.core.skills.registry import load_skill

        result = load_skill.invoke({"skill_name": "sql_query"})

        assert "# Skill: sql_query" in result
        assert "SQL" in result

    def test_load_all_builtin_skills(self):
        """Test that all built-in skills can be loaded successfully."""
        from app.core.skills.registry import load_skill, skill_registry

        for skill in skill_registry.list_skills():
            result = load_skill.invoke({"skill_name": skill.name})
            assert f"# Skill: {skill.name}" in result
            assert "not found" not in result

    def test_load_nonexistent_skill_lists_available(self):
        """Test that loading a missing skill lists available skills."""
        from app.core.skills.registry import load_skill

        result = load_skill.invoke({"skill_name": "nonexistent_xyz"})

        assert "not found" in result
        assert "sql_query" in result


class TestMCPInV1Agent:
    """Tests verifying MCP integration in V1Agent."""

    @pytest.mark.asyncio
    async def test_agent_has_mcp_initialized_flag(self):
        """Test that V1Agent has _mcp_initialized attribute."""
        from app.core.langgraph.v1.agent import V1Agent

        agent = V1Agent()
        assert hasattr(agent, "_mcp_initialized")
        assert agent._mcp_initialized is False

    @pytest.mark.asyncio
    async def test_initialize_mcp_tools_sets_flag(self):
        """Test that _initialize_mcp_tools sets the initialized flag."""
        from app.core.langgraph.v1.agent import V1Agent

        agent = V1Agent()

        with patch(
            "app.core.langgraph.v1.agent.get_mcp_tools",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await agent._initialize_mcp_tools()

        assert agent._mcp_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_mcp_tools_idempotent(self):
        """Test that _initialize_mcp_tools only runs once."""
        from app.core.langgraph.v1.agent import V1Agent

        agent = V1Agent()

        mock_get = AsyncMock(return_value=[])
        with patch("app.core.langgraph.v1.agent.get_mcp_tools", mock_get):
            await agent._initialize_mcp_tools()
            await agent._initialize_mcp_tools()

        # Should only be called once
        mock_get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialize_mcp_tools_adds_tools(self):
        """Test that MCP tools are added to the agent's tool list."""
        from app.core.langgraph.v1.agent import V1Agent

        agent = V1Agent()
        initial_tool_count = len(agent._all_tools)

        # Create mock MCP tools
        mock_tool_1 = MagicMock()
        mock_tool_1.name = "mcp_tool_1"
        mock_tool_2 = MagicMock()
        mock_tool_2.name = "mcp_tool_2"

        with patch(
            "app.core.langgraph.v1.agent.get_mcp_tools",
            new_callable=AsyncMock,
            return_value=[mock_tool_1, mock_tool_2],
        ):
            await agent._initialize_mcp_tools()

        assert len(agent._all_tools) == initial_tool_count + 2

    @pytest.mark.asyncio
    async def test_initialize_mcp_tools_handles_failure(self):
        """Test that MCP initialization failure doesn't crash the agent."""
        from app.core.langgraph.v1.agent import V1Agent

        agent = V1Agent()
        initial_tool_count = len(agent._all_tools)

        with patch(
            "app.core.langgraph.v1.agent.get_mcp_tools",
            new_callable=AsyncMock,
            side_effect=Exception("MCP connection failed"),
        ):
            await agent._initialize_mcp_tools()

        # Should still be marked as initialized (so we don't retry)
        assert agent._mcp_initialized is True
        # Tools should remain unchanged
        assert len(agent._all_tools) == initial_tool_count


class TestMCPConfigFileIntegration:
    """Tests for the MCP configuration file at project root."""

    def test_mcp_config_file_exists(self):
        """Test that mcp_servers.json exists at project root."""
        import os

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "mcp_servers.json")
        assert os.path.exists(config_path), f"mcp_servers.json not found at {config_path}"

    def test_mcp_config_file_valid_json(self):
        """Test that mcp_servers.json contains valid JSON."""
        import json
        import os

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "mcp_servers.json")

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        assert "servers" in config
        assert isinstance(config["servers"], list)

    def test_mcp_config_servers_have_required_fields(self):
        """Test that each server in mcp_servers.json has required fields."""
        import json
        import os

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "mcp_servers.json")

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        for server in config["servers"]:
            assert "name" in server, f"Server missing 'name': {server}"
            assert "transport" in server, f"Server missing 'transport': {server}"
            assert server["transport"] in ("sse", "stdio"), (
                f"Invalid transport '{server['transport']}' for server '{server['name']}'"
            )

    def test_mcp_default_servers_disabled(self):
        """Test that default example servers are disabled."""
        import json
        import os

        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "mcp_servers.json")

        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        for server in config["servers"]:
            assert server.get("enabled") is False, f"Default server '{server['name']}' should be disabled"
