"""Shared test fixtures for the test suite."""

import json
import os
import tempfile
from typing import Generator

import pytest


@pytest.fixture
def tmp_skills_dir(tmp_path) -> str:
    """Create a temporary directory with sample skill markdown files."""
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()

    # Valid skill file
    valid_skill = prompts_dir / "test_skill.md"
    valid_skill.write_text(
        "---\n"
        "name: test_skill\n"
        "description: A test skill for unit testing\n"
        "tags: test, unit\n"
        "---\n\n"
        "# Test Skill Content\n\n"
        "This is the full content of the test skill.\n"
        "It contains detailed instructions for testing.\n",
        encoding="utf-8",
    )

    # Another valid skill file
    another_skill = prompts_dir / "another_skill.md"
    another_skill.write_text(
        "---\n"
        "name: another_skill\n"
        "description: Another test skill\n"
        "tags: test\n"
        "---\n\n"
        "# Another Skill\n\n"
        "Content for another skill.\n",
        encoding="utf-8",
    )

    # Skill file without frontmatter (invalid)
    no_frontmatter = prompts_dir / "no_frontmatter.md"
    no_frontmatter.write_text(
        "# No Frontmatter\n\nThis file has no frontmatter.\n",
        encoding="utf-8",
    )

    # Skill file with missing required fields (invalid)
    missing_fields = prompts_dir / "missing_fields.md"
    missing_fields.write_text(
        "---\n"
        "name: incomplete\n"
        "---\n\n"
        "Missing description field.\n",
        encoding="utf-8",
    )

    # Skill file with no tags
    no_tags_skill = prompts_dir / "no_tags.md"
    no_tags_skill.write_text(
        "---\n"
        "name: no_tags_skill\n"
        "description: Skill without tags\n"
        "---\n\n"
        "Skill content without tags.\n",
        encoding="utf-8",
    )

    # Non-markdown file (should be ignored)
    txt_file = prompts_dir / "readme.txt"
    txt_file.write_text("This is not a markdown file.\n", encoding="utf-8")

    return str(tmp_path)


@pytest.fixture
def tmp_mcp_config(tmp_path) -> str:
    """Create a temporary MCP configuration file."""
    config = {
        "servers": [
            {
                "name": "test-sse-server",
                "transport": "sse",
                "url": "http://localhost:9999/sse",
                "enabled": True,
            },
            {
                "name": "test-stdio-server",
                "transport": "stdio",
                "command": "echo",
                "args": ["hello"],
                "env": {"TEST_VAR": "test_value"},
                "enabled": True,
            },
            {
                "name": "disabled-server",
                "transport": "sse",
                "url": "http://localhost:8888/sse",
                "enabled": False,
            },
        ]
    }
    config_path = tmp_path / "mcp_servers.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return str(config_path)


@pytest.fixture
def tmp_mcp_config_empty(tmp_path) -> str:
    """Create a temporary MCP configuration with no servers."""
    config = {"servers": []}
    config_path = tmp_path / "mcp_servers.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return str(config_path)


@pytest.fixture
def tmp_mcp_config_invalid_json(tmp_path) -> str:
    """Create a temporary MCP configuration with invalid JSON."""
    config_path = tmp_path / "mcp_servers.json"
    config_path.write_text("{invalid json content", encoding="utf-8")
    return str(config_path)
