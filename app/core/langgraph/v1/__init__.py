"""LangChain v1 Agent implementation using create_agent + Middleware pattern.

This package provides the primary agent implementation,
leveraging LangChain v1's create_agent API with composable middleware for:
- Dynamic prompt engineering
- Human-in-the-Loop approval
- Long-term memory integration
- Conversation summarization
- Multi-agent supervisor routing

Usage:
    from app.core.langgraph.v1 import V1Agent, V1MultiAgent
"""

from app.core.langgraph.v1.agent import V1Agent
from app.core.langgraph.v1.multi_agent import V1MultiAgent

__all__ = ["V1Agent", "V1MultiAgent"]
