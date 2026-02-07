"""RAGFlow retriever provider using OpenAI-compatible and retrieval APIs."""

from typing import Any, Optional

import httpx

from app.core.logging import logger
from app.core.rag.base import BaseRetriever
from app.core.rag.schema import RAGDocument


class RAGFlowRetriever(BaseRetriever):
    """Retriever that queries an external RAGFlow instance.

    Supports two modes:
    - retrieval: Direct dataset retrieval via /api/v1/datasets/{dataset_id}/retrieval
    - chat: OpenAI-compatible chat completion via /api/v1/chats_openai/{chat_id}/chat/completions

    Config keys:
        base_url: RAGFlow server URL (e.g. "http://ragflow:9380")
        api_key: RAGFlow API key
        mode: "retrieval" or "chat" (default: "retrieval")
        dataset_ids: List of dataset IDs to search (for retrieval mode)
        chat_id: Chat assistant ID (for chat mode)
        similarity_threshold: Minimum similarity score (default: 0.0)
        timeout: HTTP request timeout in seconds (default: 30)
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize RAGFlowRetriever with config."""
        super().__init__(name, config)
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        base_url = self.config.get("base_url", "http://ragflow:9380")
        api_key = self.config.get("api_key", "")
        timeout = self.config.get("timeout", 30)

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
        self._initialized = True
        logger.info("ragflow_retriever_initialized", base_url=base_url)

    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict[str, Any]] = None) -> list[RAGDocument]:
        """Retrieve documents from RAGFlow."""
        if not self._initialized or self._client is None:
            await self.initialize()

        mode = self.config.get("mode", "retrieval")
        if mode == "chat":
            return await self._retrieve_via_chat(query)
        return await self._retrieve_via_dataset(query, top_k)

    async def _retrieve_via_dataset(self, query: str, top_k: int) -> list[RAGDocument]:
        """Retrieve using RAGFlow's dataset retrieval API."""
        dataset_ids = self.config.get("dataset_ids", [])
        similarity_threshold = self.config.get("similarity_threshold", 0.0)

        if not dataset_ids:
            logger.warning("ragflow_no_dataset_ids_configured", provider=self.name)
            return []

        all_docs = []
        for dataset_id in dataset_ids:
            try:
                resp = await self._client.post(
                    f"/api/v1/datasets/{dataset_id}/retrieval",
                    json={
                        "question": query,
                        "top_k": top_k,
                        "similarity_threshold": similarity_threshold,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                chunks = data.get("data", {}).get("chunks", [])
                for chunk in chunks:
                    all_docs.append(
                        RAGDocument(
                            content=chunk.get("content", ""),
                            source=chunk.get("document_name", ""),
                            score=chunk.get("similarity", 0.0),
                            metadata={
                                "dataset_id": dataset_id,
                                "document_id": chunk.get("document_id", ""),
                                "chunk_id": chunk.get("id", ""),
                            },
                        )
                    )
            except Exception as e:
                logger.exception("ragflow_dataset_retrieval_failed", dataset_id=dataset_id, error=str(e))

        all_docs.sort(key=lambda d: d.score, reverse=True)
        return all_docs[:top_k]

    async def _retrieve_via_chat(self, query: str) -> list[RAGDocument]:
        """Retrieve using RAGFlow's OpenAI-compatible chat API and extract references."""
        chat_id = self.config.get("chat_id", "")
        if not chat_id:
            logger.warning("ragflow_no_chat_id_configured", provider=self.name)
            return []

        try:
            resp = await self._client.post(
                f"/api/v1/chats_openai/{chat_id}/chat/completions",
                json={
                    "model": "model",
                    "messages": [{"role": "user", "content": query}],
                    "stream": False,
                    "extra_body": {"reference": True},
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract content from the response
            choices = data.get("choices", [])
            if not choices:
                return []

            content = choices[0].get("message", {}).get("content", "")
            return [
                RAGDocument(
                    content=content,
                    source=f"ragflow_chat:{chat_id}",
                    score=1.0,
                    metadata={"chat_id": chat_id, "mode": "chat"},
                )
            ] if content else []

        except Exception as e:
            logger.exception("ragflow_chat_retrieval_failed", chat_id=chat_id, error=str(e))
            return []

    async def health_check(self) -> bool:
        """Check RAGFlow connectivity."""
        if self._client is None:
            return False
        try:
            resp = await self._client.get("/api/v1/datasets", params={"page": 1, "page_size": 1})
            return resp.status_code in (200, 401)
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
        self._initialized = False
