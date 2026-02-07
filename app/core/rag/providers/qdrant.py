"""Qdrant vector database retriever provider."""

from typing import Any, Optional

from app.core.logging import logger
from app.core.rag.base import BaseRetriever
from app.core.rag.schema import RAGDocument


class QdrantRetriever(BaseRetriever):
    """Retriever that queries a Qdrant vector database instance.

    Config keys:
        host: Qdrant server host (default: "qdrant")
        port: Qdrant REST port (default: 6333)
        api_key: Optional API key for authentication
        collection_name: Qdrant collection to search (default: "rag_documents")
        embedding_model: OpenAI embedding model name (default: "text-embedding-3-small")
        score_threshold: Minimum similarity score (default: 0.0)
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize QdrantRetriever with config."""
        super().__init__(name, config)
        self._client = None
        self._embeddings = None

    async def initialize(self) -> None:
        """Initialize Qdrant client and embedding model."""
        try:
            from langchain_openai import OpenAIEmbeddings
            from qdrant_client import AsyncQdrantClient

            host = self.config.get("host", "qdrant")
            port = self.config.get("port", 6333)
            api_key = self.config.get("api_key", "") or None

            self._client = AsyncQdrantClient(host=host, port=port, api_key=api_key)
            self._embeddings = OpenAIEmbeddings(model=self.config.get("embedding_model", "text-embedding-3-small"))
            self._initialized = True
            logger.info("qdrant_retriever_initialized", host=host, port=port)
        except Exception as e:
            logger.exception("qdrant_retriever_initialization_failed", error=str(e))
            raise

    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict[str, Any]] = None) -> list[RAGDocument]:
        """Retrieve documents from Qdrant by vector similarity search."""
        if not self._initialized or self._client is None or self._embeddings is None:
            await self.initialize()

        from qdrant_client.models import Filter, FieldCondition, MatchValue

        collection_name = self.config.get("collection_name", "rag_documents")
        score_threshold = self.config.get("score_threshold", 0.0)

        query_vector = await self._embeddings.aembed_query(query)

        qdrant_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = await self._client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            query_filter=qdrant_filter,
        )

        documents = []
        for point in results:
            payload = point.payload or {}
            documents.append(
                RAGDocument(
                    content=payload.get("content", payload.get("text", payload.get("page_content", ""))),
                    source=payload.get("source", ""),
                    score=point.score,
                    metadata={k: v for k, v in payload.items() if k not in ("content", "text", "page_content")},
                )
            )
        return documents

    async def health_check(self) -> bool:
        """Check Qdrant connectivity."""
        if self._client is None:
            return False
        try:
            await self._client.get_collections()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close the Qdrant client."""
        if self._client:
            await self._client.close()
        self._initialized = False
