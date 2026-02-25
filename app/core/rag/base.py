"""Base retriever interface for RAG knowledge base providers."""

from abc import ABC, abstractmethod
from typing import Any

from app.core.rag.schema import RAGDocument


class BaseRetriever(ABC):
    """Abstract base class for all RAG retriever providers.

    Every provider must implement:
    - retrieve(): async document retrieval
    - health_check(): verify connectivity

    Providers that support document management may also override:
    - list_documents(): list ingested documents
    - get_document_chunks(): get all chunks for a document
    - delete_document(): delete a document and its chunks
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

    @property
    def supports_document_management(self) -> bool:
        """Return True if this provider supports list/get/delete documents.

        Override in subclasses that implement document management.
        """
        return False

    async def list_documents(self, user_id: str = "") -> list[dict[str, Any]]:
        """List ingested documents. Override in subclasses that support this.

        Args:
            user_id: Filter by user_id if provided.

        Returns:
            List of document metadata dicts.
        """
        return []

    async def get_document_chunks(self, doc_id: str) -> list[dict[str, Any]]:
        """Get all chunks for a specific document. Override in subclasses.

        Args:
            doc_id: The document ID.

        Returns:
            List of chunk dicts with content and metadata, sorted by chunk_index.
        """
        return []

    async def delete_document(self, doc_id: str) -> bool:
        """Delete a document and its chunks. Override in subclasses.

        Args:
            doc_id: The document ID to delete.

        Returns:
            True if deleted successfully, False otherwise.
        """
        return False

    def __repr__(self) -> str:
        """Return a string representation of the retriever."""
        return f"<{self.__class__.__name__} name={self.name!r} initialized={self._initialized}>"
