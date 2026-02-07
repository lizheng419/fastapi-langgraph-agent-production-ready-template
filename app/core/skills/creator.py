"""SkillCreator — LLM-driven automatic skill generation and incremental learning.

This module provides the SkillCreator class that can:
1. Generate new skills from conversation history or user instructions
2. Incrementally update existing skills with new knowledge
3. Summarize conversations into reusable skill templates

Inspired by https://skills.sh/anthropics/skills/skill-creator
"""

from datetime import datetime
from typing import (
    List,
    Optional,
)

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from app.core.logging import logger
from app.core.skills.schema import Skill

# --- Prompts for LLM-driven skill creation ---

SKILL_CREATE_SYSTEM_PROMPT = """You are a Skill Creator — an expert at distilling conversations and instructions
into reusable, modular skill definitions for an AI agent.

A skill consists of:
- name: A unique snake_case identifier (e.g., "api_design", "data_pipeline")
- description: A concise 1-2 sentence description of what the skill does and when to use it.
  This is the PRIMARY triggering mechanism. Include both what the skill does AND specific triggers/contexts.
- tags: Comma-separated categorization tags
- content: The full skill body in Markdown — procedural instructions, checklists, examples, patterns.
  Only include information that is NON-OBVIOUS to an AI agent. Prefer concise examples over verbose explanations.

Output format (YAML frontmatter + Markdown body):
```
---
name: skill_name_here
description: Brief but comprehensive description including when to use this skill
tags: tag1, tag2, tag3
---

# Skill Title

[Markdown instructions, checklists, examples, patterns]
```

Key principles:
- Concise is key. The context window is a shared resource.
- Only add knowledge the AI doesn't already have.
- Use imperative/infinitive form in instructions.
- Prefer concrete examples over abstract explanations.
- Challenge each paragraph: "Does this justify its token cost?"
"""

SKILL_CREATE_USER_PROMPT = """Based on the following {source_type}, create a reusable skill:

{content}

Generate a complete skill definition in the specified YAML frontmatter + Markdown format.
Focus on extracting reusable patterns, procedures, and domain knowledge."""

SKILL_UPDATE_SYSTEM_PROMPT = """You are a Skill Updater — you incrementally improve existing skills
by merging new knowledge while preserving the original structure and valuable content.

Rules:
- PRESERVE all existing valuable content
- ADD new knowledge, patterns, or examples from the new information
- REMOVE only clearly outdated or contradictory information
- MAINTAIN the same YAML frontmatter format (name, description, tags)
- INCREMENT the version mentally — the caller handles version tracking
- Keep the skill CONCISE — challenge each addition: "Does this justify its token cost?"

Output the complete updated skill in the same YAML frontmatter + Markdown format."""

SKILL_UPDATE_USER_PROMPT = """Here is the existing skill:

```
---
name: {name}
description: {description}
tags: {tags}
---

{content}
```

New information to merge:

{new_info}

Output the complete updated skill with the new knowledge merged in."""

SKILL_FROM_CONVERSATION_PROMPT = """Analyze this conversation and extract reusable knowledge into a skill.

Conversation:
{conversation}

Look for:
1. Specialized workflows or multi-step procedures
2. Domain-specific patterns or best practices
3. Reusable code templates or configurations
4. Decision frameworks or troubleshooting guides
5. Any procedural knowledge that would help handle similar requests in the future

If the conversation contains valuable reusable knowledge, generate a skill.
If the conversation is too generic or casual to extract a meaningful skill, respond with exactly: NO_SKILL_FOUND

Generate a complete skill definition in the specified YAML frontmatter + Markdown format."""


class SkillCreator:
    """LLM-driven automatic skill generation and incremental learning.

    Creates new skills from conversations, instructions, or user requests.
    Supports incremental updates to existing skills with new knowledge.
    """

    def __init__(self):
        """Initialize the SkillCreator."""
        self._llm = None

    def _get_llm(self):
        """Lazily initialize the LLM instance."""
        if self._llm is None:
            from app.services.llm import LLMRegistry

            from app.core.config import settings

            self._llm = LLMRegistry.get(settings.DEFAULT_LLM_MODEL)
        return self._llm

    async def create_from_instruction(
        self,
        instruction: str,
        source: str = "agent",
    ) -> Optional[Skill]:
        """Create a new skill from a user instruction or description.

        Args:
            instruction: The instruction or description to create a skill from.
            source: Origin of the skill creation request.

        Returns:
            Optional[Skill]: The created skill, or None if creation failed.
        """
        logger.info("skill_creator_creating_from_instruction", instruction_length=len(instruction))

        messages: List[BaseMessage] = [
            SystemMessage(content=SKILL_CREATE_SYSTEM_PROMPT),
            HumanMessage(content=SKILL_CREATE_USER_PROMPT.format(
                source_type="instruction",
                content=instruction,
            )),
        ]

        try:
            llm = self._get_llm()
            response: AIMessage = await llm.ainvoke(messages)
            skill = self._parse_skill_response(response.content, source=source)

            if skill:
                logger.info("skill_creator_skill_created", skill_name=skill.name, source=source)
            else:
                logger.warning("skill_creator_failed_to_parse_response")

            return skill
        except Exception as e:
            logger.exception("skill_creator_creation_failed", error=str(e))
            return None

    async def create_from_conversation(
        self,
        messages: List[BaseMessage],
        source: str = "conversation",
    ) -> Optional[Skill]:
        """Create a new skill by analyzing a conversation history.

        Args:
            messages: The conversation history to analyze.
            source: Origin of the skill.

        Returns:
            Optional[Skill]: The extracted skill, or None if no skill found.
        """
        conversation_text = self._format_conversation(messages)
        logger.info(
            "skill_creator_creating_from_conversation",
            message_count=len(messages),
            conversation_length=len(conversation_text),
        )

        llm_messages: List[BaseMessage] = [
            SystemMessage(content=SKILL_CREATE_SYSTEM_PROMPT),
            HumanMessage(content=SKILL_FROM_CONVERSATION_PROMPT.format(
                conversation=conversation_text,
            )),
        ]

        try:
            llm = self._get_llm()
            response: AIMessage = await llm.ainvoke(llm_messages)

            if "NO_SKILL_FOUND" in response.content:
                logger.info("skill_creator_no_skill_in_conversation")
                return None

            skill = self._parse_skill_response(response.content, source=source)
            if skill:
                logger.info("skill_creator_skill_extracted", skill_name=skill.name, source=source)
            return skill
        except Exception as e:
            logger.exception("skill_creator_conversation_extraction_failed", error=str(e))
            return None

    async def update_skill(
        self,
        existing_skill: Skill,
        new_info: str,
    ) -> Optional[Skill]:
        """Incrementally update an existing skill with new knowledge.

        Args:
            existing_skill: The existing skill to update.
            new_info: New information to merge into the skill.

        Returns:
            Optional[Skill]: The updated skill, or None if update failed.
        """
        logger.info(
            "skill_creator_updating_skill",
            skill_name=existing_skill.name,
            current_version=existing_skill.version,
        )

        messages: List[BaseMessage] = [
            SystemMessage(content=SKILL_UPDATE_SYSTEM_PROMPT),
            HumanMessage(content=SKILL_UPDATE_USER_PROMPT.format(
                name=existing_skill.name,
                description=existing_skill.description,
                tags=", ".join(existing_skill.tags),
                content=existing_skill.content,
                new_info=new_info,
            )),
        ]

        try:
            llm = self._get_llm()
            response: AIMessage = await llm.ainvoke(messages)
            updated_skill = self._parse_skill_response(
                response.content,
                source=existing_skill.source,
            )

            if updated_skill:
                updated_skill.version = existing_skill.version + 1
                updated_skill.created_at = existing_skill.created_at
                updated_skill.updated_at = datetime.now()
                updated_skill.auto_generated = existing_skill.auto_generated

                logger.info(
                    "skill_creator_skill_updated",
                    skill_name=updated_skill.name,
                    new_version=updated_skill.version,
                )
            return updated_skill
        except Exception as e:
            logger.exception("skill_creator_update_failed", error=str(e))
            return None

    def _format_conversation(self, messages: List[BaseMessage]) -> str:
        """Format conversation messages into readable text.

        Args:
            messages: List of conversation messages.

        Returns:
            str: Formatted conversation text.
        """
        lines = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "User"
            elif isinstance(msg, AIMessage):
                role = "Assistant"
            elif isinstance(msg, SystemMessage):
                continue
            else:
                role = "System"
            lines.append(f"**{role}**: {msg.content}")
        return "\n\n".join(lines)

    def _parse_skill_response(
        self,
        response: str,
        source: str = "agent",
    ) -> Optional[Skill]:
        """Parse LLM response into a Skill object.

        Extracts YAML frontmatter and Markdown body from the response.

        Args:
            response: The raw LLM response text.
            source: Origin of the skill.

        Returns:
            Optional[Skill]: Parsed skill or None if parsing fails.
        """
        text = response.strip()

        # Strip wrapping code fences if present
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3].strip()

        # Find YAML frontmatter
        if not text.startswith("---"):
            logger.warning("skill_creator_response_missing_frontmatter")
            return None

        parts = text.split("---", 2)
        if len(parts) < 3:
            logger.warning("skill_creator_response_invalid_frontmatter")
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
            logger.warning("skill_creator_response_missing_required_fields", metadata_keys=list(metadata.keys()))
            return None

        tags = [t.strip() for t in metadata.get("tags", "").split(",") if t.strip()]

        now = datetime.now()
        return Skill(
            name=name,
            description=description,
            content=body,
            tags=tags,
            version=1,
            source=source,
            auto_generated=True,
            created_at=now,
            updated_at=now,
        )


# Global SkillCreator instance
skill_creator = SkillCreator()
