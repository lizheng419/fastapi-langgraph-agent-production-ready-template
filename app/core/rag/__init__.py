"""RAG (Retrieval-Augmented Generation) knowledge base integration.

This package provides a pluggable retriever architecture that supports
multiple knowledge base backends:
- Qdrant (local vector database)
- pgvector (shared PostgreSQL instance)
- RAGFlow (external RAG engine, OpenAI-compatible API)
- Generic HTTP (any external REST API: Dify, FastGPT, etc.)
"""

from app.core.rag.base import BaseRetriever
from app.core.rag.manager import RetrieverManager
from app.core.rag.schema import (
    RAGDocument,
    RetrievalQuery,
    RetrievalResult,
)

__all__ = [
    "BaseRetriever",
    "RetrieverManager",
    "RAGDocument",
    "RetrievalQuery",
    "RetrievalResult",
]
