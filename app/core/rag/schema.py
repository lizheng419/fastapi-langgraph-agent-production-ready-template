"""RAG schema definitions for documents and retrieval results."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RAGDocument:
    """A document retrieved from a knowledge base."""

    content: str
    source: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_context_string(self) -> str:
        """Format this document as a context string for LLM consumption."""
        parts = [self.content]
        if self.source:
            parts.append(f"(Source: {self.source})")
        return " ".join(parts)


@dataclass
class RetrievalQuery:
    """A query to retrieve documents from knowledge bases."""

    query: str
    top_k: int = 5
    filters: dict[str, Any] = field(default_factory=dict)
    provider_names: Optional[list[str]] = None


@dataclass
class RetrievalResult:
    """Aggregated result from one or more retriever providers."""

    documents: list[RAGDocument] = field(default_factory=list)
    provider_name: str = ""
    error: Optional[str] = None

    @property
    def has_results(self) -> bool:
        """Return True if this result contains any documents."""
        return len(self.documents) > 0

    def to_context_string(self) -> str:
        """Format all documents as a combined context string."""
        if not self.documents:
            return ""
        return "\n\n".join(f"[{i + 1}] {doc.to_context_string()}" for i, doc in enumerate(self.documents))
