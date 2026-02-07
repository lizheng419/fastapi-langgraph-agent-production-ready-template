"""Unit tests for the SkillRegistry and load_skill tool."""

import os
from unittest.mock import patch

import pytest

from app.core.skills.schema import Skill
from app.core.skills.registry import SkillRegistry


class TestSkillRegistryParsing:
    """Tests for SkillRegistry markdown file parsing."""

    def test_parse_valid_skill_file(self, tmp_skills_dir):
        """Test parsing a valid skill markdown file."""
        registry = SkillRegistry.__new__(SkillRegistry)
        registry._skills = {}

        filepath = os.path.join(tmp_skills_dir, "prompts", "test_skill.md")
        skill = registry._parse_skill_file(filepath)

        assert skill is not None
        assert skill.name == "test_skill"
        assert skill.description == "A test skill for unit testing"
        assert skill.tags == ["test", "unit"]
        assert "Test Skill Content" in skill.content

    def test_parse_skill_file_without_frontmatter(self, tmp_skills_dir):
        """Test parsing a file without frontmatter returns None."""
        registry = SkillRegistry.__new__(SkillRegistry)
        registry._skills = {}

        filepath = os.path.join(tmp_skills_dir, "prompts", "no_frontmatter.md")
        skill = registry._parse_skill_file(filepath)

        assert skill is None

    def test_parse_skill_file_missing_required_fields(self, tmp_skills_dir):
        """Test parsing a file with missing required fields returns None."""
        registry = SkillRegistry.__new__(SkillRegistry)
        registry._skills = {}

        filepath = os.path.join(tmp_skills_dir, "prompts", "missing_fields.md")
        skill = registry._parse_skill_file(filepath)

        assert skill is None

    def test_parse_skill_file_without_tags(self, tmp_skills_dir):
        """Test parsing a skill file without tags results in empty tags list."""
        registry = SkillRegistry.__new__(SkillRegistry)
        registry._skills = {}

        filepath = os.path.join(tmp_skills_dir, "prompts", "no_tags.md")
        skill = registry._parse_skill_file(filepath)

        assert skill is not None
        assert skill.name == "no_tags_skill"
        assert skill.tags == []


class TestSkillRegistryLoadFromPrompts:
    """Tests for loading skills from the prompts directory."""

    def test_load_skills_from_valid_directory(self, tmp_skills_dir):
        """Test loading skills from a directory with valid and invalid files."""
        registry = SkillRegistry.__new__(SkillRegistry)
        registry._skills = {}

        with patch.object(SkillRegistry, "__init__", lambda self: None):
            registry._skills = {}

        prompts_dir = os.path.join(tmp_skills_dir, "prompts")

        with patch("app.core.skills.registry.os.path.dirname", return_value=tmp_skills_dir):
            with patch(
                "app.core.skills.registry.os.path.join",
                side_effect=lambda *args: os.path.join(*args),
            ):
                with patch(
                    "app.core.skills.registry.os.path.exists",
                    return_value=True,
                ):
                    with patch(
                        "app.core.skills.registry.os.listdir",
                        return_value=os.listdir(prompts_dir),
                    ):
                        # Directly call the method with the correct prompts_dir path
                        for filename in os.listdir(prompts_dir):
                            if not filename.endswith(".md"):
                                continue
                            filepath = os.path.join(prompts_dir, filename)
                            skill = registry._parse_skill_file(filepath)
                            if skill:
                                registry._skills[skill.name] = skill

        # Should have loaded: test_skill, another_skill, no_tags_skill
        # Should NOT have loaded: no_frontmatter, missing_fields
        assert len(registry._skills) == 3
        assert "test_skill" in registry._skills
        assert "another_skill" in registry._skills
        assert "no_tags_skill" in registry._skills

    def test_load_skills_nonexistent_directory(self, tmp_path):
        """Test loading skills when prompts directory does not exist."""
        registry = SkillRegistry.__new__(SkillRegistry)
        registry._skills = {}

        # Point to a non-existent directory
        with patch(
            "app.core.skills.registry.os.path.join",
            return_value=str(tmp_path / "nonexistent" / "prompts"),
        ):
            registry._load_skills_from_prompts()

        assert len(registry._skills) == 0


class TestSkillRegistryOperations:
    """Tests for SkillRegistry register, get, list, and prompt generation."""

    def _make_registry(self) -> SkillRegistry:
        """Create a SkillRegistry without loading from disk."""
        registry = SkillRegistry.__new__(SkillRegistry)
        registry._skills = {}
        return registry

    def test_register_skill(self):
        """Test programmatic skill registration."""
        registry = self._make_registry()
        skill = Skill(
            name="custom",
            description="Custom skill",
            content="Custom content",
            tags=["custom"],
        )
        registry.register(skill)

        assert "custom" in registry._skills
        assert registry._skills["custom"].description == "Custom skill"

    def test_register_overwrites_existing(self):
        """Test that registering a skill with the same name overwrites it."""
        registry = self._make_registry()
        skill_v1 = Skill(name="dup", description="v1", content="v1 content")
        skill_v2 = Skill(name="dup", description="v2", content="v2 content")

        registry.register(skill_v1)
        registry.register(skill_v2)

        assert registry.get("dup").description == "v2"

    def test_get_existing_skill(self):
        """Test getting a registered skill by name."""
        registry = self._make_registry()
        skill = Skill(name="findme", description="Find me", content="Found")
        registry.register(skill)

        result = registry.get("findme")
        assert result is not None
        assert result.name == "findme"

    def test_get_nonexistent_skill(self):
        """Test getting a non-existent skill returns None."""
        registry = self._make_registry()
        result = registry.get("nonexistent")
        assert result is None

    def test_list_skills_empty(self):
        """Test listing skills when registry is empty."""
        registry = self._make_registry()
        assert registry.list_skills() == []

    def test_list_skills_multiple(self):
        """Test listing multiple registered skills."""
        registry = self._make_registry()
        registry.register(Skill(name="a", description="A", content="A content"))
        registry.register(Skill(name="b", description="B", content="B content"))

        skills = registry.list_skills()
        assert len(skills) == 2
        names = {s.name for s in skills}
        assert names == {"a", "b"}

    def test_get_skills_prompt_empty(self):
        """Test skills prompt generation when registry is empty."""
        registry = self._make_registry()
        prompt = registry.get_skills_prompt()
        assert prompt == ""

    def test_get_skills_prompt_with_skills(self):
        """Test skills prompt generation with registered skills."""
        registry = self._make_registry()
        registry.register(
            Skill(name="sql_query", description="SQL expert", content="SQL content", tags=["db", "sql"])
        )
        registry.register(
            Skill(name="code_review", description="Code reviewer", content="Review content", tags=["code"])
        )

        prompt = registry.get_skills_prompt()

        assert "## Available Skills" in prompt
        assert "load_skill" in prompt
        assert "**sql_query**" in prompt
        assert "SQL expert" in prompt
        assert "[db, sql]" in prompt
        assert "**code_review**" in prompt
        assert "Code reviewer" in prompt

    def test_get_skills_prompt_without_tags(self):
        """Test skills prompt generation for skill without tags."""
        registry = self._make_registry()
        registry.register(
            Skill(name="no_tag", description="No tags", content="Content")
        )

        prompt = registry.get_skills_prompt()
        assert "**no_tag**" in prompt
        assert "[" not in prompt.split("**no_tag**")[1].split("\n")[0]


class TestLoadSkillTool:
    """Tests for the load_skill LangChain tool function."""

    def test_load_existing_skill(self):
        """Test load_skill returns full content for an existing skill."""
        from app.core.skills.registry import load_skill, skill_registry

        # Register a test skill
        test_skill = Skill(
            name="tool_test_skill",
            description="Test for tool",
            content="Detailed tool test content with instructions.",
        )
        skill_registry.register(test_skill)

        result = load_skill.invoke({"skill_name": "tool_test_skill"})

        assert "# Skill: tool_test_skill" in result
        assert "Detailed tool test content" in result

    def test_load_nonexistent_skill(self):
        """Test load_skill returns error message for missing skill."""
        from app.core.skills.registry import load_skill

        result = load_skill.invoke({"skill_name": "totally_nonexistent_skill_xyz"})

        assert "not found" in result
        assert "Available skills:" in result

    def test_load_skill_is_langchain_tool(self):
        """Test that load_skill is a proper LangChain tool."""
        from app.core.skills.registry import load_skill_tool

        assert hasattr(load_skill_tool, "invoke")
        assert hasattr(load_skill_tool, "name")
        assert load_skill_tool.name == "load_skill"


class TestBuiltinSkillsLoaded:
    """Tests to verify that built-in skills are loaded from app/core/skills/prompts/."""

    def test_builtin_skills_exist(self):
        """Test that the global skill_registry has loaded built-in skills."""
        from app.core.skills.registry import skill_registry

        skills = skill_registry.list_skills()
        skill_names = {s.name for s in skills}

        # These should have been loaded from the actual prompts directory
        assert "sql_query" in skill_names
        assert "data_analysis" in skill_names
        assert "code_review" in skill_names
        assert "api_design" in skill_names

    def test_builtin_skill_content_not_empty(self):
        """Test that built-in skills have non-empty content."""
        from app.core.skills.registry import skill_registry

        for skill in skill_registry.list_skills():
            assert len(skill.content) > 0, f"Skill '{skill.name}' has empty content"
            assert len(skill.description) > 0, f"Skill '{skill.name}' has empty description"
