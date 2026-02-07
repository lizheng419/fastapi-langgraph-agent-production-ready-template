"""Skills system for progressive disclosure of agent capabilities.

This package implements the Skills pattern from LangChain documentation,
enabling the agent to load specialized prompt-based instructions on-demand
rather than upfront, reducing context usage and improving scalability.

Includes SkillCreator for LLM-driven automatic skill generation and
incremental learning from conversations.
"""

from app.core.skills.creator import (
    SkillCreator,
    skill_creator,
)
from app.core.skills.registry import (
    create_skill_tool,
    list_all_skills_tool,
    load_skill_tool,
    skill_registry,
    update_skill_tool,
)
from app.core.skills.schema import Skill

__all__ = [
    "Skill",
    "SkillCreator",
    "skill_creator",
    "skill_registry",
    "load_skill_tool",
    "create_skill_tool",
    "update_skill_tool",
    "list_all_skills_tool",
]
