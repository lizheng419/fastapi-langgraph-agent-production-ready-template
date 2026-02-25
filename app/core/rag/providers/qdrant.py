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

    async def retrieve(
        self, query: str, top_k: int = 5, filters: Optional[dict[str, Any]] = None
    ) -> list[RAGDocument]:
        """Retrieve documents from Qdrant by vector similarity search."""
        if not self._initialized or self._client is None or self._embeddings is None:
            await self.initialize()

        from qdrant_client.models import FieldCondition, Filter, MatchValue

        collection_name = self.config.get("collection_name", "rag_documents")
        score_threshold = self.config.get("score_threshold", 0.0)

        query_vector = await self._embeddings.aembed_query(query)

        qdrant_filter = None
        if filters:
            conditions = [FieldCondition(key=k, match=MatchValue(value=v)) for k, v in filters.items()]
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

    @property
    def supports_document_management(self) -> bool:
        """Qdrant supports document management."""
        return True

    async def list_documents(self, user_id: str = "") -> list[dict[str, Any]]:
        """List ingested documents by querying unique doc_ids from Qdrant."""
        if not self._initialized or self._client is None:
            await self.initialize()

        from qdrant_client.models import FieldCondition, Filter, MatchValue

        collection_name = self.config.get("collection_name", "rag_documents")

        try:
            collections = await self._client.get_collections()
            existing_names = [c.name for c in collections.collections]
            if collection_name not in existing_names:
                return []

            scroll_filter = None
            if user_id:
                scroll_filter = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])

            seen_docs: dict[str, dict[str, Any]] = {}
            offset = None

            while True:
                results = await self._client.scroll(
                    collection_name=collection_name,
                    scroll_filter=scroll_filter,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                points, next_offset = results

                for point in points:
                    payload = point.payload or {}
                    doc_id = payload.get("doc_id", "")
                    if doc_id and doc_id not in seen_docs:
                        seen_docs[doc_id] = {
                            "doc_id": doc_id,
                            "filename": payload.get("source", ""),
                            "user_id": payload.get("user_id", ""),
                            "created_at": payload.get("created_at", ""),
                            "chunk_index": payload.get("chunk_index", 0),
                            "provider": self.name,
                        }
                    elif doc_id and doc_id in seen_docs:
                        ci = payload.get("chunk_index", 0)
                        if ci > seen_docs[doc_id].get("chunk_index", 0):
                            seen_docs[doc_id]["chunk_index"] = ci

                if next_offset is None:
                    break
                offset = next_offset

            documents = []
            for doc_id, info in seen_docs.items():
                documents.append(
                    {
                        "doc_id": doc_id,
                        "filename": info["filename"],
                        "user_id": info["user_id"],
                        "created_at": info["created_at"],
                        "chunk_count": info["chunk_index"] + 1,
                        "provider": self.name,
                    }
                )

            documents.sort(key=lambda d: d.get("created_at", ""), reverse=True)
            return documents
        except Exception as e:
            logger.exception("qdrant_list_documents_failed", error=str(e))
            return []

    async def get_document_chunks(self, doc_id: str) -> list[dict[str, Any]]:
        """Get all chunks for a specific document from Qdrant."""
        if not self._initialized or self._client is None:
            await self.initialize()

        from qdrant_client.models import FieldCondition, Filter, MatchValue

        collection_name = self.config.get("collection_name", "rag_documents")

        try:
            collections = await self._client.get_collections()
            existing_names = [c.name for c in collections.collections]
            if collection_name not in existing_names:
                return []

            scroll_filter = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])

            chunks: list[dict[str, Any]] = []
            offset = None

            while True:
                results = await self._client.scroll(
                    collection_name=collection_name,
                    scroll_filter=scroll_filter,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                points, next_offset = results

                for point in points:
                    payload = point.payload or {}
                    chunks.append(
                        {
                            "chunk_index": payload.get("chunk_index", 0),
                            "content": payload.get("text", ""),
                            "source": payload.get("source", ""),
                            "doc_id": payload.get("doc_id", ""),
                            "user_id": payload.get("user_id", ""),
                            "created_at": payload.get("created_at", ""),
                            "provider": self.name,
                        }
                    )

                if next_offset is None:
                    break
                offset = next_offset

            chunks.sort(key=lambda c: c["chunk_index"])
            return chunks
        except Exception as e:
            logger.exception("qdrant_get_chunks_failed", doc_id=doc_id, error=str(e))
            return []

    async def delete_document(self, doc_id: str) -> bool:
        """Delete all chunks belonging to a document from Qdrant."""
        if not self._initialized or self._client is None:
            await self.initialize()

        from qdrant_client.models import FieldCondition, Filter, MatchValue

        collection_name = self.config.get("collection_name", "rag_documents")

        try:
            await self._client.delete(
                collection_name=collection_name,
                points_selector=Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))]),
            )
            logger.info("qdrant_document_deleted", doc_id=doc_id, collection=collection_name)
            return True
        except Exception as e:
            logger.exception("qdrant_delete_document_failed", doc_id=doc_id, error=str(e))
            return False
