"""V1 Chatbot API endpoints using LangChain v1 create_agent + Middleware.

Provides the same endpoints as the legacy chatbot.py but powered by:
- langchain.agents.create_agent (replacing manual StateGraph)
- Composable middleware (HITL, memory, tracing, metrics)
- Support for both single-agent and multi-agent modes

API prefix: /chatbot
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import StreamingResponse

from app.api.v1.auth import get_current_session
from app.api.v1.sse import sse_event_generator
from app.core.config import settings
from app.core.langgraph.v1.agent import V1Agent
from app.core.langgraph.v1.multi_agent import V1MultiAgent
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.session import Session
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
)

router = APIRouter()

# Singleton instances
_single_agent = V1Agent()
_multi_agent = V1MultiAgent()


def _get_agent(mode: str):
    """Get the appropriate agent based on mode."""
    if mode == "multi":
        return _multi_agent
    return _single_agent


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def chat_v1(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
    mode: str = Query(default="single", description="Agent mode: 'single' or 'multi'"),
):
    """Process a chat request using LangChain v1 create_agent.

    Args:
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing messages.
        session: The current session from the auth token.
        mode: Agent mode — 'single' for V1Agent, 'multi' for V1MultiAgent.

    Returns:
        ChatResponse: The processed chat response.
    """
    try:
        logger.info(
            "v1_chat_request_received",
            session_id=session.id,
            mode=mode,
            message_count=len(chat_request.messages),
        )

        agent = _get_agent(mode)
        result = await agent.get_response(
            chat_request.messages,
            session.id,
            user_id=session.user_id,
        )

        logger.info("v1_chat_request_processed", session_id=session.id, mode=mode)
        return ChatResponse(messages=result)

    except Exception as e:
        logger.exception("v1_chat_request_failed", session_id=session.id, mode=mode, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def chat_stream_v1(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
    mode: str = Query(default="single", description="Agent mode: 'single' or 'multi'"),
):
    """Process a chat request with streaming using LangChain v1.

    Args:
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing messages.
        session: The current session from the auth token.
        mode: Agent mode — 'single' or 'multi'.

    Returns:
        StreamingResponse: SSE stream of chat completion tokens.
    """
    try:
        logger.info(
            "v1_stream_request_received",
            session_id=session.id,
            mode=mode,
            message_count=len(chat_request.messages),
        )

        agent = _get_agent(mode)

        stream = agent.get_stream_response(
            chat_request.messages,
            session.id,
            user_id=session.user_id,
        )

        return StreamingResponse(
            sse_event_generator(stream, session.id, log_event_name="v1_stream_failed"),
            media_type="text/event-stream",
        )

    except Exception as e:
        logger.exception("v1_stream_setup_failed", session_id=session.id, mode=mode, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/messages", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def get_session_messages_v1(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Get all messages for a session (V1 agent).

    Args:
        request: The FastAPI request object for rate limiting.
        session: The current session from the auth token.

    Returns:
        ChatResponse: All messages in the session.
    """
    try:
        messages = await _single_agent.get_chat_history(session.id)
        return ChatResponse(messages=messages)
    except Exception as e:
        logger.exception("v1_get_messages_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/messages")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["messages"][0])
async def clear_chat_history_v1(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """Clear all messages for a session (V1 agent).

    Args:
        request: The FastAPI request object for rate limiting.
        session: The current session from the auth token.

    Returns:
        dict: Confirmation message.
    """
    try:
        await _single_agent.clear_chat_history(session.id)
        return {"message": "Chat history cleared successfully"}
    except Exception as e:
        logger.exception("v1_clear_history_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
