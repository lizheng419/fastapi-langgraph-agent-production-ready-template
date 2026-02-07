"""RAG retriever provider implementations.

Each provider wraps a specific knowledge base backend and implements
the BaseRetriever interface.
"""

from app.core.rag.providers.http import GenericHTTPRetriever
from app.core.rag.providers.pgvector import PgvectorRetriever
from app.core.rag.providers.qdrant import QdrantRetriever
from app.core.rag.providers.ragflow import RAGFlowRetriever

PROVIDER_REGISTRY: dict[str, type] = {
    "qdrant": QdrantRetriever,
    "pgvector": PgvectorRetriever,
    "ragflow": RAGFlowRetriever,
    "http": GenericHTTPRetriever,
}

__all__ = [
    "PROVIDER_REGISTRY",
    "QdrantRetriever",
    "PgvectorRetriever",
    "RAGFlowRetriever",
    "GenericHTTPRetriever",
]
