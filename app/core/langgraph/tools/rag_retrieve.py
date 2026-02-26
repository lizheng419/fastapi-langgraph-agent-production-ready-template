"""RAG knowledge base retrieval tool for LangGraph.

This tool allows the agent to search across configured knowledge base
providers (Qdrant, pgvector, RAGFlow, Dify, FastGPT, custom HTTP APIs).
"""

from langchain_core.tools import tool

from app.core.logging import logger
from app.core.rag.manager import get_shared_manager
from app.core.rag.schema import RetrievalQuery


@tool
async def retrieve_knowledge(query: str, top_k: int = 5, provider: str = "") -> str:
    """Search knowledge bases for information relevant to the query.

    Use this tool when you need to look up specific information from
    the configured knowledge bases (internal documents, RAGFlow, Dify,
    FastGPT, or other connected systems).

    IMPORTANT: When you use information from the retrieved documents in your
    response, you MUST cite the source by including a "📚 Knowledge Base Sources"
    section at the end of your response listing which documents were used.

    Args:
        query: The search query describing what information you need.
        top_k: Maximum number of documents to retrieve (default: 5).
        provider: Optional specific provider name to search. Leave empty to search all enabled providers.

    Returns:
        Retrieved knowledge base documents formatted as context.
    """
    try:
        manager = await get_shared_manager()

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

        result_parts = [
            "=== Knowledge Base Results ===",
            f"Query: {query}",
            f"Documents found: {len(docs)}",
            "",
        ]
        for i, doc in enumerate(docs):
            source = doc.source or "unknown"
            provider_name = doc.metadata.get("provider", "")
            entry = f"[Doc {i + 1}] (Source: {source}"
            if provider_name:
                entry += f", Provider: {provider_name}"
            entry += f")\n{doc.content}"
            result_parts.append(entry)

        result_parts.append("")
        result_parts.append(
            "=== INSTRUCTION: When using the above information in your response, "
            "add a '📚 Knowledge Base Sources' section at the end listing the "
            "source document names used. ==="
        )

        return "\n\n".join(result_parts)

    except Exception as e:
        logger.exception("rag_tool_execution_failed", error=str(e))
        return f"Knowledge base retrieval failed: {str(e)}"
