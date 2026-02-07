"""Skill registry and load_skill tool for progressive disclosure."""

import os
from datetime import datetime
from typing import (
    Dict,
    List,
    Optional,
)

from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from app.core.logging import logger
from app.core.skills.schema import Skill


class SkillRegistry:
    """Registry for managing and loading agent skills.

    Skills are loaded from markdown files in the prompts directory.
    Each skill has a lightweight description (shown in system prompt)
    and full content (loaded on-demand via tool calls).

    Auto-generated skills are persisted to the _auto/ subdirectory
    and loaded on startup alongside manual skills.
    """

    def __init__(self):
        """Initialize the skill registry."""
        self._skills: Dict[str, Skill] = {}
        self._prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
        self._auto_dir = os.path.join(self._prompts_dir, "_auto")
        self._load_skills_from_prompts()

    def _load_skills_from_prompts(self) -> None:
        """Load skills from markdown files in the prompts directory and _auto/ subdirectory."""
        # Load manual skills
        self._load_skills_from_directory(self._prompts_dir, source="manual")
        # Load auto-generated skills
        self._load_skills_from_directory(self._auto_dir, source="agent")

    def _load_skills_from_directory(self, directory: str, source: str = "manual") -> None:
        """Load skills from markdown files in a specific directory.

        Args:
            directory: Path to the directory containing skill files.
            source: Default source label for loaded skills.
        """
        if not os.path.exists(directory):
            if source == "agent":
                os.makedirs(directory, exist_ok=True)
                logger.info("skills_auto_directory_created", path=directory)
            else:
                logger.warning("skills_prompts_directory_not_found", path=directory)
            return

        for filename in os.listdir(directory):
            if not filename.endswith(".md"):
                continue

            filepath = os.path.join(directory, filename)
            # Skip subdirectories
            if os.path.isdir(filepath):
                continue

            try:
                skill = self._parse_skill_file(filepath, default_source=source)
                if skill:
                    self._skills[skill.name] = skill
                    logger.info("skill_loaded", skill_name=skill.name, source=skill.source)
            except Exception as e:
                logger.exception("skill_loading_failed", filename=filename, error=str(e))

    def _parse_skill_file(self, filepath: str, default_source: str = "manual") -> Optional[Skill]:
        """Parse a skill markdown file.

        Expected format:
        ---
        name: skill_name
        description: Brief description
        tags: tag1, tag2
        ---
        Full skill content here...

        Args:
            filepath: Path to the skill markdown file.
            default_source: Default source if not specified in frontmatter.

        Returns:
            Optional[Skill]: Parsed skill or None if parsing fails.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse frontmatter
        if not content.startswith("---"):
            logger.warning("skill_file_missing_frontmatter", filepath=filepath)
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            logger.warning("skill_file_invalid_frontmatter", filepath=filepath)
            return None

        frontmatter = parts[1].strip()
        body = parts[2].strip()

        # Parse frontmatter fields
        metadata = {}
        for line in frontmatter.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

        name = metadata.get("name")
        description = metadata.get("description")
        if not name or not description:
            logger.warning("skill_file_missing_required_fields", filepath=filepath)
            return None

        tags = [t.strip() for t in metadata.get("tags", "").split(",") if t.strip()]
        source = metadata.get("source", default_source)
        version = int(metadata.get("version", "1"))
        auto_generated = metadata.get("auto_generated", "false").lower() == "true"

        return Skill(
            name=name,
            description=description,
            content=body,
            tags=tags,
            version=version,
            source=source,
            auto_generated=auto_generated,
        )

    def register(self, skill: Skill) -> None:
        """Register a skill programmatically.

        Args:
            skill: The skill to register.
        """
        self._skills[skill.name] = skill
        logger.info("skill_registered", skill_name=skill.name)

    def register_or_update(self, skill: Skill, persist: bool = True) -> Skill:
        """Register a new skill or update an existing one (incremental).

        If a skill with the same name exists, increments the version
        and updates timestamps. Optionally persists to _auto/ directory.

        Args:
            skill: The skill to register or update.
            persist: Whether to persist the skill to disk.

        Returns:
            Skill: The registered/updated skill.
        """
        existing = self._skills.get(skill.name)
        now = datetime.now()

        if existing:
            skill.version = existing.version + 1
            skill.created_at = existing.created_at or now
            skill.updated_at = now
            logger.info(
                "skill_updated_incrementally",
                skill_name=skill.name,
                old_version=existing.version,
                new_version=skill.version,
            )
        else:
            skill.created_at = skill.created_at or now
            skill.updated_at = now

        self._skills[skill.name] = skill

        if persist and skill.auto_generated:
            self._save_skill_to_file(skill)

        logger.info(
            "skill_registered_or_updated",
            skill_name=skill.name,
            version=skill.version,
            auto_generated=skill.auto_generated,
        )
        return skill

    def unregister(self, name: str) -> bool:
        """Remove a skill from the registry.

        Args:
            name: The skill name to remove.

        Returns:
            bool: True if removed, False if not found.
        """
        if name in self._skills:
            skill = self._skills.pop(name)
            logger.info("skill_unregistered", skill_name=name)

            # Also remove the file if auto-generated
            if skill.auto_generated:
                filepath = os.path.join(self._auto_dir, f"{name}.md")
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info("skill_file_deleted", filepath=filepath)
            return True

        logger.warning("skill_unregister_not_found", skill_name=name)
        return False

    def _save_skill_to_file(self, skill: Skill) -> None:
        """Persist a skill to the _auto/ directory as a markdown file.

        Args:
            skill: The skill to save.
        """
        os.makedirs(self._auto_dir, exist_ok=True)
        filepath = os.path.join(self._auto_dir, f"{skill.name}.md")

        tag_str = ", ".join(skill.tags) if skill.tags else ""
        frontmatter_lines = [
            "---",
            f"name: {skill.name}",
            f"description: {skill.description}",
            f"tags: {tag_str}",
            f"version: {skill.version}",
            f"source: {skill.source}",
            "auto_generated: true",
            "---",
        ]
        content = "\n".join(frontmatter_lines) + "\n\n" + skill.content + "\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("skill_persisted_to_file", skill_name=skill.name, filepath=filepath)

    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name.

        Args:
            name: The skill name.

        Returns:
            Optional[Skill]: The skill if found, None otherwise.
        """
        return self._skills.get(name)

    def list_skills(self) -> List[Skill]:
        """List all registered skills.

        Returns:
            List[Skill]: All registered skills.
        """
        return list(self._skills.values())

    def get_skills_prompt(self) -> str:
        """Generate the skills section for the system prompt.

        Returns a lightweight description of all available skills
        for inclusion in the system prompt.

        Returns:
            str: Formatted skills prompt section.
        """
        if not self._skills:
            return ""

        lines = ["## Available Skills", ""]
        lines.append("Use the `load_skill` tool to load detailed instructions for a specific skill when needed.")
        lines.append("Use the `create_skill` tool to create a new skill from instructions or conversation patterns.")
        lines.append("Use the `update_skill` tool to incrementally improve an existing skill with new knowledge.")
        lines.append("")
        for skill in self._skills.values():
            tag_str = f" [{', '.join(skill.tags)}]" if skill.tags else ""
            auto_str = " (auto)" if skill.auto_generated else ""
            lines.append(f"- **{skill.name}** (v{skill.version}){auto_str}: {skill.description}{tag_str}")

        return "\n".join(lines)


# Global skill registry instance
skill_registry = SkillRegistry()


@tool
def load_skill(skill_name: str, runtime: ToolRuntime) -> str:
    """Load the full content of a specialized skill into context.

    Use this tool when you need detailed instructions, schemas, or business logic
    for handling a specific type of request. This provides comprehensive guidelines
    for the skill area.

    Args:
        skill_name: The name of the skill to load (e.g., "sql_query", "data_analysis").
        runtime: Injected by LangChain — provides access to context, state, and store.
    """
    user_id = getattr(runtime.context, "user_id", None) if runtime and runtime.context else None
    skill = skill_registry.get(skill_name)
    if skill:
        logger.info("skill_loaded_by_agent", skill_name=skill_name, user_id=user_id)
        return f"# Skill: {skill.name}\n\n{skill.content}"

    available = ", ".join(s.name for s in skill_registry.list_skills())
    logger.warning("skill_not_found", requested_skill=skill_name, available_skills=available, user_id=user_id)
    return f"Skill '{skill_name}' not found. Available skills: {available}"


@tool
async def create_skill(instruction: str, runtime: ToolRuntime) -> str:
    """Create a new reusable skill from instructions or a description.

    Use this tool when the user asks you to "learn this", "remember this pattern",
    "create a skill for X", or when you identify reusable knowledge worth preserving.
    The skill will be auto-generated by LLM analysis and persisted for future use.

    Args:
        instruction: A description of what the skill should do, including examples,
                     procedures, patterns, or domain knowledge to capture.
        runtime: Injected by LangChain — provides access to context, state, and store.
    """
    from app.core.skills.creator import skill_creator

    user_id = getattr(runtime.context, "user_id", None) if runtime and runtime.context else None
    logger.info("create_skill_tool_invoked", instruction_length=len(instruction), user_id=user_id)

    skill = await skill_creator.create_from_instruction(instruction, source="agent")
    if not skill:
        return "Failed to create skill from the given instruction. Please provide more specific details."

    registered = skill_registry.register_or_update(skill, persist=True)
    return (
        f"Skill '{registered.name}' created successfully (v{registered.version}).\n"
        f"Description: {registered.description}\n"
        f"Tags: {', '.join(registered.tags)}\n"
        f"The skill is now available via `load_skill('{registered.name}')` for future use."
    )


@tool
async def update_skill(skill_name: str, new_info: str, runtime: ToolRuntime) -> str:
    """Incrementally update an existing skill with new knowledge.

    Use this tool when you discover new patterns, corrections, or improvements
    that should be merged into an existing skill. The existing content is preserved
    and new knowledge is intelligently merged.

    Args:
        skill_name: Name of the existing skill to update.
        new_info: New information, patterns, or corrections to merge into the skill.
        runtime: Injected by LangChain — provides access to context, state, and store.
    """
    from app.core.skills.creator import skill_creator

    user_id = getattr(runtime.context, "user_id", None) if runtime and runtime.context else None
    existing = skill_registry.get(skill_name)
    if not existing:
        available = ", ".join(s.name for s in skill_registry.list_skills())
        return f"Skill '{skill_name}' not found. Available skills: {available}"

    logger.info("update_skill_tool_invoked", skill_name=skill_name, new_info_length=len(new_info), user_id=user_id)

    updated = await skill_creator.update_skill(existing, new_info)
    if not updated:
        return f"Failed to update skill '{skill_name}'. Please try again with different input."

    registered = skill_registry.register_or_update(updated, persist=True)
    return (
        f"Skill '{registered.name}' updated to v{registered.version}.\n"
        f"Description: {registered.description}\n"
        f"The updated skill content is now available via `load_skill('{registered.name}')`."
    )


@tool
def list_all_skills(runtime: ToolRuntime) -> str:
    """List all available skills with their details.

    Use this tool to see all registered skills including their version,
    source, and whether they were auto-generated.

    Args:
        runtime: Injected by LangChain — provides access to context, state, and store.
    """
    skills = skill_registry.list_skills()
    if not skills:
        return "No skills registered."

    lines = [f"Total skills: {len(skills)}\n"]
    for s in skills:
        auto_str = " [auto-generated]" if s.auto_generated else " [manual]"
        tag_str = f" Tags: {', '.join(s.tags)}" if s.tags else ""
        lines.append(f"- **{s.name}** (v{s.version}){auto_str}: {s.description}{tag_str}")
    return "\n".join(lines)


# Export the tools
load_skill_tool = load_skill
create_skill_tool = create_skill
update_skill_tool = update_skill
list_all_skills_tool = list_all_skills
