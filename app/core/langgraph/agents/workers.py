"""Worker agents for the Multi-Agent system.

Each worker is a specialized agent with a focused system prompt and
optional dedicated tools. Workers are invoked by the Supervisor.
"""

from typing import (
    Dict,
    List,
    Optional,
)

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.tools.base import BaseTool

from app.core.logging import logger
from app.services.llm import llm_service


class BaseWorker:
    """Base class for all worker agents.

    Attributes:
        name: Unique identifier for this worker.
        description: Brief description used by the Supervisor for routing.
        system_prompt: The system prompt defining this worker's persona.
        tools: Optional list of tools this worker can use.
    """

    name: str = "base_worker"
    description: str = "A base worker agent."
    system_prompt: str = "You are a helpful assistant."

    def __init__(self, tools: Optional[List[BaseTool]] = None):
        """Initialize the worker agent."""
        self.tools = tools or []
        self.llm_service = llm_service

    async def invoke(self, messages: list, **kwargs) -> AIMessage:
        """Process messages and return a response.

        Args:
            messages: The conversation messages to process.

        Returns:
            AIMessage: The worker's response.
        """
        # Prepend the worker's system prompt
        full_messages = [{"role": "system", "content": self.system_prompt}]
        for msg in messages:
            if hasattr(msg, "content"):
                role = getattr(msg, "type", "user")
                if role == "human":
                    role = "user"
                elif role == "ai":
                    role = "assistant"
                full_messages.append({"role": role, "content": msg.content})
            elif isinstance(msg, dict):
                full_messages.append(msg)

        try:
            if self.tools:
                self.llm_service.bind_tools(self.tools)

            response = await self.llm_service.call(full_messages)

            logger.info(
                "worker_response_generated",
                worker_name=self.name,
            )
            return response
        except Exception as e:
            logger.exception("worker_invocation_failed", worker_name=self.name, error=str(e))
            return AIMessage(content=f"[{self.name}] I encountered an error processing your request: {str(e)}")


class ResearcherWorker(BaseWorker):
    """Research specialist worker for information gathering and analysis."""

    name = "researcher"
    description = "Specializes in web search, information gathering, fact-checking, and summarizing findings."
    system_prompt = (
        "You are an expert researcher. Your strengths:\n"
        "- Thorough web searching and information gathering\n"
        "- Fact-checking and source verification\n"
        "- Summarizing complex findings clearly\n"
        "- Providing well-structured research reports\n\n"
        "Always cite sources when possible. Present findings in a clear, organized format."
    )


class CoderWorker(BaseWorker):
    """Coding specialist worker for code generation and review."""

    name = "coder"
    description = "Specializes in writing code, debugging, code review, and technical architecture."
    system_prompt = (
        "You are an expert software engineer. Your strengths:\n"
        "- Writing clean, production-ready code\n"
        "- Debugging and troubleshooting\n"
        "- Code review with security and performance focus\n"
        "- Technical architecture and design patterns\n"
        "- Multiple languages: Python, JavaScript, TypeScript, SQL, etc.\n\n"
        "Always follow best practices. Include error handling and type hints. "
        "Explain your code decisions."
    )


class AnalystWorker(BaseWorker):
    """Data analysis specialist worker."""

    name = "analyst"
    description = "Specializes in data analysis, statistics, visualization recommendations, and business insights."
    system_prompt = (
        "You are an expert data analyst. Your strengths:\n"
        "- Statistical analysis and interpretation\n"
        "- Data visualization recommendations\n"
        "- Business intelligence and insights\n"
        "- SQL query optimization\n"
        "- Clear presentation of quantitative findings\n\n"
        "Always explain your methodology. Present results with context and actionable recommendations."
    )


# Registry of all available workers
WORKER_REGISTRY: Dict[str, BaseWorker] = {
    "researcher": ResearcherWorker(),
    "coder": CoderWorker(),
    "analyst": AnalystWorker(),
}


def get_worker(name: str) -> Optional[BaseWorker]:
    """Get a worker by name.

    Args:
        name: The worker name.

    Returns:
        Optional[BaseWorker]: The worker if found, None otherwise.
    """
    return WORKER_REGISTRY.get(name)


def list_workers() -> List[Dict[str, str]]:
    """List all available workers with their descriptions.

    Returns:
        List[Dict[str, str]]: Worker name and description pairs.
    """
    return [{"name": w.name, "description": w.description} for w in WORKER_REGISTRY.values()]


def get_worker_configs() -> Dict[str, dict]:
    """Export worker definitions as config dicts for create_agent consumers.

    Returns:
        Dict mapping worker name to {"system_prompt": ..., "description": ...}.
    """
    return {
        name: {"system_prompt": w.system_prompt, "description": w.description} for name, w in WORKER_REGISTRY.items()
    }


def register_worker(
    name: str,
    system_prompt: str,
    description: str,
    tools: Optional[List[BaseTool]] = None,
) -> None:
    """Register a new worker into the global WORKER_REGISTRY.

    Args:
        name: Unique worker name.
        system_prompt: The worker's system prompt.
        description: Brief description for routing.
        tools: Optional tools for the worker.
    """
    worker = BaseWorker(tools=tools)
    worker.name = name
    worker.description = description
    worker.system_prompt = system_prompt
    WORKER_REGISTRY[name] = worker
    logger.info("worker_registered", worker=name)
