"""Shared SSE (Server-Sent Events) helper for streaming endpoints.

Provides a reusable async generator that converts an agent/workflow
token stream into SSE-formatted events.
"""

import json
from typing import AsyncGenerator

from app.core.logging import logger
from app.schemas.chat import StreamResponse


async def sse_event_generator(
    stream: AsyncGenerator[str, None],
    session_id: str,
    log_event_name: str = "stream_failed",
) -> AsyncGenerator[str, None]:
    r"""Convert an async token stream into SSE events.

    Yields ``data: {json}\n\n`` lines suitable for ``StreamingResponse``.

    Args:
        stream: Async generator yielding string chunks.
        session_id: Session ID for error logging.
        log_event_name: Event name used in structured log on failure.

    Yields:
        SSE-formatted strings: one per chunk, plus a final ``done=True`` event.
    """
    try:
        async for chunk in stream:
            response = StreamResponse(content=chunk, done=False)
            yield f"data: {json.dumps(response.model_dump())}\n\n"

        final_response = StreamResponse(content="", done=True)
        yield f"data: {json.dumps(final_response.model_dump())}\n\n"

    except Exception as e:
        logger.exception(log_event_name, session_id=session_id, error=str(e))
        error_response = StreamResponse(content=str(e), done=True)
        yield f"data: {json.dumps(error_response.model_dump())}\n\n"
