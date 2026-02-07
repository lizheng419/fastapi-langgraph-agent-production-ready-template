"""RAG knowledge base retrieval tool for LangGraph.

This tool allows the agent to search across configured knowledge base
providers (Qdrant, pgvector, RAGFlow, Dify, FastGPT, custom HTTP APIs).
"""

from typing import Optional

from langchain_core.tools import tool

from app.core.logging import logger
from app.core.rag.manager import RetrieverManager, load_providers_from_config
from app.core.rag.schema import RetrievalQuery

_manager: Optional[RetrieverManager] = None


async def _get_manager() -> RetrieverManager:
    """Get or create the global RetrieverManager singleton."""
    global _manager
    if _manager is None:
        _manager = load_providers_from_config()
        await _manager.initialize_all()
    return _manager


@tool
async def retrieve_knowledge(query: str, top_k: int = 5, provider: str = "") -> str:
    """Search knowledge bases for information relevant to the query.

    Use this tool when you need to look up specific information from
    the configured knowledge bases (internal documents, RAGFlow, Dify,
    FastGPT, or other connected systems).

    Args:
        query: The search query describing what information you need.
        top_k: Maximum number of documents to retrieve (default: 5).
        provider: Optional specific provider name to search. Leave empty to search all enabled providers.

    Returns:
        Retrieved knowledge base documents formatted as context.
    """
    try:
        manager = await _get_manager()

        if not manager.provider_names:
            return "No knowledge base providers are configured. Check rag_providers.json."

        retrieval_query = RetrievalQuery(
            query=query,
            top_k=top_k,
            provider_names=[provider] if provider else None,
        )

        docs = await manager.retrieve_and_merge(retrieval_query)

        if not docs:
            return f"No relevant documents found for: {query}"

        result_parts = []
        for i, doc in enumerate(docs):
            entry = f"[{i + 1}] {doc.content}"
            if doc.source:
                entry += f"\n   Source: {doc.source}"
            if doc.metadata.get("provider"):
                entry += f" (via {doc.metadata['provider']})"
            result_parts.append(entry)

        return "\n\n".join(result_parts)

    except Exception as e:
        logger.exception("rag_tool_execution_failed", error=str(e))
        return f"Knowledge base retrieval failed: {str(e)}"
