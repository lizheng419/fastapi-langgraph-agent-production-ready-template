"""RAG Retriever Manager — registry, routing, and aggregation."""

import asyncio
import json
import os
from typing import Any, Optional

from app.core.logging import logger
from app.core.rag.base import BaseRetriever
from app.core.rag.schema import (
    RAGDocument,
    RetrievalQuery,
    RetrievalResult,
)


class RetrieverManager:
    """Manages multiple retriever providers with pluggable configuration.

    Loads provider config from a JSON file, instantiates providers,
    and routes queries to one or more backends.
    """

    def __init__(self):
        """Initialize the RetrieverManager."""
        self._providers: dict[str, BaseRetriever] = {}
        self._initialized = False

    def register(self, provider: BaseRetriever) -> None:
        """Register a retriever provider.

        Args:
            provider: A BaseRetriever instance.
        """
        self._providers[provider.name] = provider
        logger.info("rag_provider_registered", provider=provider.name, type=provider.__class__.__name__)

    def get_provider(self, name: str) -> Optional[BaseRetriever]:
        """Get a registered provider by name.

        Args:
            name: Provider name.

        Returns:
            The BaseRetriever instance or None.
        """
        return self._providers.get(name)

    @property
    def provider_names(self) -> list[str]:
        """Return list of registered provider names."""
        return list(self._providers.keys())

    async def initialize_all(self) -> None:
        """Initialize all registered providers."""
        for name, provider in self._providers.items():
            try:
                await provider.initialize()
                logger.info("rag_provider_initialized", provider=name)
            except Exception as e:
                logger.exception("rag_provider_initialization_failed", provider=name, error=str(e))
        self._initialized = True

    async def close_all(self) -> None:
        """Close all registered providers."""
        for name, provider in self._providers.items():
            try:
                await provider.close()
            except Exception as e:
                logger.exception("rag_provider_close_failed", provider=name, error=str(e))
        self._initialized = False

    async def retrieve(self, query: RetrievalQuery) -> list[RetrievalResult]:
        """Retrieve documents from one or more providers.

        Args:
            query: RetrievalQuery with query text, top_k, filters, and optional provider names.

        Returns:
            List of RetrievalResult, one per queried provider.
        """
        target_names = query.provider_names or list(self._providers.keys())
        targets = {n: p for n, p in self._providers.items() if n in target_names}

        if not targets:
            logger.warning("rag_no_providers_available", requested=target_names)
            return []

        async def _query_provider(name: str, provider: BaseRetriever) -> RetrievalResult:
            try:
                docs = await provider.retrieve(query.query, top_k=query.top_k, filters=query.filters)
                logger.info(
                    "rag_retrieval_completed",
                    provider=name,
                    query=query.query[:100],
                    result_count=len(docs),
                )
                return RetrievalResult(documents=docs, provider_name=name)
            except Exception as e:
                logger.exception("rag_retrieval_failed", provider=name, error=str(e))
                return RetrievalResult(provider_name=name, error=str(e))

        results = await asyncio.gather(*[_query_provider(n, p) for n, p in targets.items()])
        return list(results)

    async def retrieve_and_merge(self, query: RetrievalQuery, dedup: bool = True) -> list[RAGDocument]:
        """Retrieve from all targeted providers and merge results by score.

        Args:
            query: The retrieval query.
            dedup: Whether to deduplicate by content.

        Returns:
            Merged list of RAGDocument sorted by score descending.
        """
        results = await self.retrieve(query)
        all_docs: list[RAGDocument] = []
        for result in results:
            if result.has_results:
                for doc in result.documents:
                    if not doc.metadata.get("provider"):
                        doc.metadata["provider"] = result.provider_name
                    all_docs.append(doc)

        if dedup:
            seen = set()
            unique_docs = []
            for doc in all_docs:
                key = doc.content.strip()[:200]
                if key not in seen:
                    seen.add(key)
                    unique_docs.append(doc)
            all_docs = unique_docs

        all_docs.sort(key=lambda d: d.score, reverse=True)
        return all_docs[: query.top_k]

    async def list_all_documents(self, user_id: str = "") -> list[dict[str, Any]]:
        """List documents from all providers that support document management.

        Args:
            user_id: Filter by user_id if provided.

        Returns:
            Aggregated list of document metadata dicts from all providers.
        """
        all_docs: list[dict[str, Any]] = []
        for name, provider in self._providers.items():
            if not provider.supports_document_management:
                continue
            try:
                docs = await provider.list_documents(user_id=user_id)
                all_docs.extend(docs)
            except Exception as e:
                logger.exception("rag_list_documents_failed", provider=name, error=str(e))

        all_docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
        return all_docs

    async def get_document_chunks(self, doc_id: str, provider_name: str = "") -> list[dict[str, Any]]:
        """Get all chunks for a document from the appropriate provider.

        Args:
            doc_id: The document ID.
            provider_name: Optional provider name hint. If empty, tries all providers.

        Returns:
            List of chunk dicts with content and metadata.
        """
        if provider_name:
            provider = self._providers.get(provider_name)
            if provider and provider.supports_document_management:
                return await provider.get_document_chunks(doc_id)
            return []

        for name, provider in self._providers.items():
            if not provider.supports_document_management:
                continue
            try:
                chunks = await provider.get_document_chunks(doc_id)
                if chunks:
                    return chunks
            except Exception as e:
                logger.exception("rag_get_chunks_failed", provider=name, doc_id=doc_id, error=str(e))

        return []

    async def delete_document(self, doc_id: str, provider_name: str = "") -> bool:
        """Delete a document from the appropriate provider.

        Args:
            doc_id: The document ID to delete.
            provider_name: Optional provider name hint. If empty, tries all providers.

        Returns:
            True if deleted from at least one provider.
        """
        if provider_name:
            provider = self._providers.get(provider_name)
            if provider and provider.supports_document_management:
                return await provider.delete_document(doc_id)
            return False

        for name, provider in self._providers.items():
            if not provider.supports_document_management:
                continue
            try:
                deleted = await provider.delete_document(doc_id)
                if deleted:
                    return True
            except Exception as e:
                logger.exception("rag_delete_document_failed", provider=name, doc_id=doc_id, error=str(e))

        return False

    async def health_check_all(self) -> dict[str, bool]:
        """Run health checks on all providers.

        Returns:
            Dict mapping provider name to health status.
        """
        results = {}
        for name, provider in self._providers.items():
            try:
                results[name] = await provider.health_check()
            except Exception:
                results[name] = False
        return results


_global_manager: Optional[RetrieverManager] = None


async def get_shared_manager(config_path: str | None = None) -> RetrieverManager:
    """Get or create the shared global RetrieverManager singleton.

    This ensures only one manager instance (and one set of provider
    connections) exists across the entire application — used by both
    the API endpoints and the agent retrieve_knowledge tool.
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = load_providers_from_config(config_path)
        await _global_manager.initialize_all()
    return _global_manager


def load_providers_from_config(config_path: str | None = None) -> RetrieverManager:
    """Load retriever providers from a JSON configuration file.

    Args:
        config_path: Path to rag_providers.json. Defaults to project root.

    Returns:
        Configured RetrieverManager instance.
    """
    from app.core.rag.providers import PROVIDER_REGISTRY

    if config_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        config_path = os.path.join(base_dir, "rag_providers.json")

    manager = RetrieverManager()

    if not os.path.isfile(config_path):
        logger.warning("rag_config_not_found", path=config_path)
        return manager

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
    except Exception as e:
        logger.exception("rag_config_load_failed", path=config_path, error=str(e))
        return manager

    providers_config = config_data.get("providers", [])
    for entry in providers_config:
        provider_type = entry.get("type", "")
        provider_name = entry.get("name", "")
        enabled = entry.get("enabled", True)
        provider_config = entry.get("config", {})

        if not enabled:
            logger.info("rag_provider_skipped_disabled", provider=provider_name)
            continue

        provider_cls = PROVIDER_REGISTRY.get(provider_type)
        if provider_cls is None:
            logger.warning("rag_provider_type_unknown", type=provider_type, name=provider_name)
            continue

        try:
            provider = provider_cls(name=provider_name, config=provider_config)
            manager.register(provider)
        except Exception as e:
            logger.exception("rag_provider_creation_failed", name=provider_name, error=str(e))

    logger.info("rag_providers_loaded", count=len(manager.provider_names), providers=manager.provider_names)
    return manager
