"""pgvector retriever provider using the shared PostgreSQL instance."""

from typing import Any, Optional

from app.core.logging import logger
from app.core.rag.base import BaseRetriever
from app.core.rag.schema import RAGDocument


class PgvectorRetriever(BaseRetriever):
    """Retriever that queries pgvector on the main PostgreSQL database.

    Config keys:
        host: PostgreSQL host (default from settings.POSTGRES_HOST)
        port: PostgreSQL port (default from settings.POSTGRES_PORT)
        dbname: Database name (default from settings.POSTGRES_DB)
        user: Database user (default from settings.POSTGRES_USER)
        password: Database password (default from settings.POSTGRES_PASSWORD)
        collection_name: pgvector collection (default: "rag_documents")
        embedding_model: OpenAI embedding model name (default: "text-embedding-3-small")
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize PgvectorRetriever with config."""
        super().__init__(name, config)
        self._store = None
        self._embeddings = None

    def _get_connection_string(self) -> str:
        """Build the PostgreSQL connection string from config or settings."""
        from urllib.parse import quote_plus

        from app.core.config import settings

        host = self.config.get("host", settings.POSTGRES_HOST)
        port = self.config.get("port", settings.POSTGRES_PORT)
        dbname = self.config.get("dbname", settings.POSTGRES_DB)
        user = self.config.get("user", settings.POSTGRES_USER)
        password = self.config.get("password", settings.POSTGRES_PASSWORD)
        return f"postgresql+psycopg://{quote_plus(str(user))}:{quote_plus(str(password))}@{host}:{port}/{dbname}"

    async def initialize(self) -> None:
        """Initialize the pgvector store and embedding model."""
        try:
            from langchain_openai import OpenAIEmbeddings
            from langchain_postgres import PGVector

            self._embeddings = OpenAIEmbeddings(model=self.config.get("embedding_model", "text-embedding-3-small"))
            collection_name = self.config.get("collection_name", "rag_documents")

            self._store = PGVector(
                embeddings=self._embeddings,
                collection_name=collection_name,
                connection=self._get_connection_string(),
                use_jsonb=True,
            )
            self._initialized = True
            logger.info("pgvector_retriever_initialized", collection=collection_name)
        except Exception as e:
            logger.exception("pgvector_retriever_initialization_failed", error=str(e))
            raise

    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict[str, Any]] = None) -> list[RAGDocument]:
        """Retrieve documents from pgvector by similarity search."""
        if not self._initialized or self._store is None:
            await self.initialize()

        try:
            results = await self._store.asimilarity_search_with_score(query, k=top_k, filter=filters)
        except Exception as e:
            logger.exception("pgvector_retrieval_failed", error=str(e))
            return []

        documents = []
        for doc, score in results:
            documents.append(
                RAGDocument(
                    content=doc.page_content,
                    source=doc.metadata.get("source", ""),
                    score=float(score),
                    metadata={k: v for k, v in doc.metadata.items() if k != "source"},
                )
            )
        return documents

    async def health_check(self) -> bool:
        """Check PostgreSQL connectivity."""
        try:
            import asyncpg

            from app.core.config import settings

            host = self.config.get("host", settings.POSTGRES_HOST)
            port = self.config.get("port", settings.POSTGRES_PORT)
            dbname = self.config.get("dbname", settings.POSTGRES_DB)
            user = self.config.get("user", settings.POSTGRES_USER)
            password = self.config.get("password", settings.POSTGRES_PASSWORD)

            conn = await asyncpg.connect(host=host, port=port, database=dbname, user=user, password=password)
            await conn.execute("SELECT 1")
            await conn.close()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """Close pgvector store resources."""
        self._store = None
        self._initialized = False
