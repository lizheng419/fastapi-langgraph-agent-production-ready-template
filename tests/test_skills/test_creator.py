"""Unit tests for the SkillCreator LLM-driven skill generation."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.skills.creator import SkillCreator
from app.core.skills.schema import Skill


class TestSkillCreatorParsing:
    """Tests for SkillCreator._parse_skill_response parsing logic."""

    def setup_method(self):
        """Create a fresh SkillCreator for each test."""
        self.creator = SkillCreator()

    def test_parse_valid_response(self):
        """Test parsing a well-formed YAML frontmatter + Markdown response."""
        response = (
            "---\n"
            "name: api_design\n"
            "description: Best practices for RESTful API design\n"
            "tags: api, rest, design\n"
            "---\n\n"
            "# API Design\n\n"
            "Use nouns for resources, verbs for actions.\n"
        )
        skill = self.creator._parse_skill_response(response, source="agent")
        assert skill is not None
        assert skill.name == "api_design"
        assert skill.description == "Best practices for RESTful API design"
        assert skill.tags == ["api", "rest", "design"]
        assert "Use nouns" in skill.content
        assert skill.auto_generated is True
        assert skill.version == 1
        assert skill.source == "agent"

    def test_parse_response_with_code_fences(self):
        """Test parsing response wrapped in markdown code fences."""
        response = (
            "```markdown\n"
            "---\n"
            "name: docker_tips\n"
            "description: Docker best practices\n"
            "tags: docker\n"
            "---\n\n"
            "# Docker Tips\n\n"
            "Use multi-stage builds.\n"
            "```"
        )
        skill = self.creator._parse_skill_response(response)
        assert skill is not None
        assert skill.name == "docker_tips"

    def test_parse_response_missing_frontmatter(self):
        """Test that response without frontmatter returns None."""
        response = "Just some text without frontmatter."
        skill = self.creator._parse_skill_response(response)
        assert skill is None

    def test_parse_response_missing_name(self):
        """Test that response missing name field returns None."""
        response = (
            "---\n"
            "description: Some description\n"
            "tags: test\n"
            "---\n\n"
            "Content here.\n"
        )
        skill = self.creator._parse_skill_response(response)
        assert skill is None

    def test_parse_response_missing_description(self):
        """Test that response missing description field returns None."""
        response = (
            "---\n"
            "name: some_skill\n"
            "tags: test\n"
            "---\n\n"
            "Content here.\n"
        )
        skill = self.creator._parse_skill_response(response)
        assert skill is None

    def test_parse_response_no_tags(self):
        """Test that response with empty tags still parses."""
        response = (
            "---\n"
            "name: minimal_skill\n"
            "description: A minimal skill\n"
            "---\n\n"
            "Content.\n"
        )
        skill = self.creator._parse_skill_response(response)
        assert skill is not None
        assert skill.tags == []


class TestSkillCreatorFormatConversation:
    """Tests for SkillCreator._format_conversation."""

    def setup_method(self):
        """Create a fresh SkillCreator for each test."""
        self.creator = SkillCreator()

    def test_format_human_and_ai_messages(self):
        """Test formatting mixed message types."""
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ]
        result = self.creator._format_conversation(messages)
        assert "**User**: Hello" in result
        assert "**Assistant**: Hi there!" in result
        # System messages should be skipped
        assert "helpful assistant" not in result

    def test_format_empty_messages(self):
        """Test formatting empty message list."""
        result = self.creator._format_conversation([])
        assert result == ""


class TestSkillCreatorAsync:
    """Tests for async SkillCreator methods with mocked LLM."""

    def setup_method(self):
        """Create a fresh SkillCreator for each test."""
        self.creator = SkillCreator()

    @pytest.mark.asyncio
    async def test_create_from_instruction_success(self):
        """Test successful skill creation from instruction."""
        mock_response = MagicMock()
        mock_response.content = (
            "---\n"
            "name: test_skill\n"
            "description: A test skill\n"
            "tags: test\n"
            "---\n\n"
            "# Test\n\nTest content.\n"
        )
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        self.creator._llm = mock_llm

        skill = await self.creator.create_from_instruction("Create a test skill")
        assert skill is not None
        assert skill.name == "test_skill"
        assert skill.auto_generated is True

    @pytest.mark.asyncio
    async def test_create_from_instruction_llm_failure(self):
        """Test graceful handling of LLM failure."""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM error"))
        self.creator._llm = mock_llm

        skill = await self.creator.create_from_instruction("Create a test skill")
        assert skill is None

    @pytest.mark.asyncio
    async def test_create_from_conversation_no_skill(self):
        """Test conversation that yields no skill."""
        from langchain_core.messages import AIMessage, HumanMessage

        mock_response = MagicMock()
        mock_response.content = "NO_SKILL_FOUND"
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        self.creator._llm = mock_llm

        messages = [
            HumanMessage(content="Hi"),
            AIMessage(content="Hello!"),
        ]
        skill = await self.creator.create_from_conversation(messages)
        assert skill is None

    @pytest.mark.asyncio
    async def test_update_skill_increments_version(self):
        """Test that updating a skill increments its version."""
        existing = Skill(
            name="existing_skill",
            description="Original",
            content="Original content",
            tags=["test"],
            version=2,
            source="manual",
            auto_generated=False,
            created_at=datetime(2025, 1, 1),
        )
        mock_response = MagicMock()
        mock_response.content = (
            "---\n"
            "name: existing_skill\n"
            "description: Updated description\n"
            "tags: test, updated\n"
            "---\n\n"
            "# Updated\n\nNew content.\n"
        )
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        self.creator._llm = mock_llm

        updated = await self.creator.update_skill(existing, "New information")
        assert updated is not None
        assert updated.version == 3
        assert updated.created_at == datetime(2025, 1, 1)
        assert updated.auto_generated is False
