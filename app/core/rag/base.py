"""Base retriever interface for RAG knowledge base providers."""

from abc import ABC, abstractmethod
from typing import Any

from app.core.rag.schema import RAGDocument


class BaseRetriever(ABC):
    """Abstract base class for all RAG retriever providers.

    Every provider must implement:
    - retrieve(): async document retrieval
    - health_check(): verify connectivity
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize the retriever.

        Args:
            name: Unique provider name for identification.
            config: Provider-specific configuration dictionary.
        """
        self.name = name
        self.config = config
        self._initialized = False

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5, filters: dict[str, Any] | None = None) -> list[RAGDocument]:
        """Retrieve relevant documents for a given query.

        Args:
            query: The search query string.
            top_k: Maximum number of documents to return.
            filters: Optional metadata filters.

        Returns:
            List of RAGDocument objects sorted by relevance.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the retriever backend is healthy and reachable.

        Returns:
            True if the backend is available, False otherwise.
        """

    async def initialize(self) -> None:
        """Optional async initialization hook. Override if needed."""
        self._initialized = True

    async def close(self) -> None:
        """Optional cleanup hook. Override if needed."""
        self._initialized = False

    def __repr__(self) -> str:
        """Return a string representation of the retriever."""
        return f"<{self.__class__.__name__} name={self.name!r} initialized={self._initialized}>"
