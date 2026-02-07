"""Unit tests for the Skill data model."""

import pytest
from pydantic import ValidationError

from app.core.skills.schema import Skill


class TestSkillModel:
    """Tests for the Skill Pydantic model."""

    def test_create_skill_with_all_fields(self):
        """Test creating a Skill with all fields populated."""
        skill = Skill(
            name="test_skill",
            description="A test skill",
            content="Full content here",
            tags=["test", "unit"],
        )
        assert skill.name == "test_skill"
        assert skill.description == "A test skill"
        assert skill.content == "Full content here"
        assert skill.tags == ["test", "unit"]

    def test_create_skill_without_tags(self):
        """Test creating a Skill without tags defaults to empty list."""
        skill = Skill(
            name="no_tags",
            description="Skill without tags",
            content="Some content",
        )
        assert skill.tags == []

    def test_create_skill_missing_name_raises(self):
        """Test that missing name field raises ValidationError."""
        with pytest.raises(ValidationError):
            Skill(
                description="Missing name",
                content="Content",
            )

    def test_create_skill_missing_description_raises(self):
        """Test that missing description field raises ValidationError."""
        with pytest.raises(ValidationError):
            Skill(
                name="missing_desc",
                content="Content",
            )

    def test_create_skill_missing_content_raises(self):
        """Test that missing content field raises ValidationError."""
        with pytest.raises(ValidationError):
            Skill(
                name="missing_content",
                description="Missing content",
            )

    def test_skill_serialization(self):
        """Test Skill model serialization to dict."""
        skill = Skill(
            name="serialize_test",
            description="Serialization test",
            content="Content for serialization",
            tags=["a", "b"],
        )
        data = skill.model_dump()
        assert data["name"] == "serialize_test"
        assert data["description"] == "Serialization test"
        assert data["content"] == "Content for serialization"
        assert data["tags"] == ["a", "b"]

    def test_skill_empty_tags_list(self):
        """Test Skill with explicitly empty tags list."""
        skill = Skill(
            name="empty_tags",
            description="Empty tags",
            content="Content",
            tags=[],
        )
        assert skill.tags == []

    def test_skill_with_multiline_content(self):
        """Test Skill with multiline content."""
        content = "# Title\n\nParagraph 1\n\n## Section\n\n- Item 1\n- Item 2"
        skill = Skill(
            name="multiline",
            description="Multiline content",
            content=content,
        )
        assert "# Title" in skill.content
        assert "- Item 1" in skill.content
