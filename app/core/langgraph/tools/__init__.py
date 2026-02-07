"""LangGraph tools for enhanced language model capabilities.

This package contains custom tools that can be used with LangGraph to extend
the capabilities of language models. Includes tools for web search,
skill loading (progressive disclosure), skill creation (auto-generation),
and MCP server integrations.
"""

from langchain_core.tools.base import BaseTool

from app.core.skills import (
    create_skill_tool,
    list_all_skills_tool,
    load_skill_tool,
    update_skill_tool,
)

from .duckduckgo_search import duckduckgo_search_tool
from .rag_retrieve import retrieve_knowledge

tools: list[BaseTool] = [
    duckduckgo_search_tool,
    load_skill_tool,
    create_skill_tool,
    update_skill_tool,
    list_all_skills_tool,
    retrieve_knowledge,
]
