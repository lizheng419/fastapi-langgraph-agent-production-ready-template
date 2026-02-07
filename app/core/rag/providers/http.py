"""Generic HTTP retriever provider for any external REST API knowledge base.

Supports Dify, FastGPT, or any custom knowledge base API that returns
documents via HTTP.
"""

from typing import Any, Optional

import httpx

from app.core.logging import logger
from app.core.rag.base import BaseRetriever
from app.core.rag.schema import RAGDocument


class GenericHTTPRetriever(BaseRetriever):
    """Retriever that queries any external knowledge base via REST API.

    The response is parsed using configurable JSON paths so you can
    map any API response format to RAGDocument fields.

    Config keys:
        base_url: API server URL (e.g. "http://dify:3000")
        endpoint: Retrieval endpoint path (e.g. "/v1/knowledge/retrieve")
        method: HTTP method, "GET" or "POST" (default: "POST")
        api_key: API key for Authorization header
        auth_header: Auth header name (default: "Authorization")
        auth_prefix: Auth value prefix (default: "Bearer")
        timeout: Request timeout in seconds (default: 30)
        request_body_template: JSON body template with {query} and {top_k} placeholders
        response_docs_path: Dot-separated path to docs array in response (e.g. "data.records")
        response_content_key: Key for document content (default: "content")
        response_source_key: Key for document source (default: "source")
        response_score_key: Key for relevance score (default: "score")
        extra_headers: Additional HTTP headers dict
    """

    def __init__(self, name: str, config: dict[str, Any]):
        """Initialize GenericHTTPRetriever with config."""
        super().__init__(name, config)
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        base_url = self.config.get("base_url", "")
        api_key = self.config.get("api_key", "")
        auth_header = self.config.get("auth_header", "Authorization")
        auth_prefix = self.config.get("auth_prefix", "Bearer")
        timeout = self.config.get("timeout", 30)
        extra_headers = self.config.get("extra_headers", {})

        headers = {"Content-Type": "application/json", **extra_headers}
        if api_key:
            headers[auth_header] = f"{auth_prefix} {api_key}"

        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=timeout,
        )
        self._initialized = True
        logger.info("http_retriever_initialized", base_url=base_url, provider=self.name)

    async def retrieve(self, query: str, top_k: int = 5, filters: Optional[dict[str, Any]] = None) -> list[RAGDocument]:
        """Retrieve documents from the external API."""
        if not self._initialized or self._client is None:
            await self.initialize()

        endpoint = self.config.get("endpoint", "/retrieve")
        method = self.config.get("method", "POST").upper()

        # Build request body from template or default
        body_template = self.config.get("request_body_template")
        if body_template:
            body = self._render_template(body_template, query=query, top_k=top_k, filters=filters)
        else:
            body = {"query": query, "top_k": top_k}
            if filters:
                body["filters"] = filters

        try:
            if method == "GET":
                resp = await self._client.get(endpoint, params=body)
            else:
                resp = await self._client.post(endpoint, json=body)

            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.exception("http_retrieval_request_failed", provider=self.name, error=str(e))
            return []

        return self._parse_response(data)

    def _render_template(self, template: dict, query: str, top_k: int, filters: Optional[dict] = None) -> dict:
        """Render a request body template by replacing placeholders.

        Args:
            template: Dict template with string values that may contain {query}, {top_k}.
            query: The search query.
            top_k: Number of results.
            filters: Optional filters.

        Returns:
            Rendered dict.
        """
        import copy
        import json

        rendered = copy.deepcopy(template)
        raw = json.dumps(rendered)
        raw = raw.replace("{query}", query.replace('"', '\\"'))
        raw = raw.replace("{top_k}", str(top_k))
        return json.loads(raw)

    def _parse_response(self, data: Any) -> list[RAGDocument]:
        """Parse API response into RAGDocument list using configured JSON paths.

        Args:
            data: The parsed JSON response.

        Returns:
            List of RAGDocument.
        """
        docs_path = self.config.get("response_docs_path", "data")
        content_key = self.config.get("response_content_key", "content")
        source_key = self.config.get("response_source_key", "source")
        score_key = self.config.get("response_score_key", "score")

        # Navigate to the docs array using dot-separated path
        items = data
        if docs_path:
            for key in docs_path.split("."):
                if isinstance(items, dict):
                    items = items.get(key, [])
                elif isinstance(items, list) and key.isdigit():
                    items = items[int(key)] if int(key) < len(items) else []
                else:
                    items = []
                    break

        if not isinstance(items, list):
            items = [items] if items else []

        documents = []
        for item in items:
            if not isinstance(item, dict):
                continue
            documents.append(
                RAGDocument(
                    content=str(item.get(content_key, "")),
                    source=str(item.get(source_key, "")),
                    score=float(item.get(score_key, 0.0)),
                    metadata={k: v for k, v in item.items() if k not in (content_key, source_key, score_key)},
                )
            )
        return documents

    async def health_check(self) -> bool:
        """Check API connectivity."""
        if self._client is None:
            return False
        try:
            resp = await self._client.get("/")
            return resp.status_code < 500
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
        self._initialized = False
