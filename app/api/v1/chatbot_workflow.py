"""Workflow API endpoints for multi-step orchestrated workflows.

Provides endpoints for executing freely composable workflows using the
Orchestrator-Worker pattern with LangGraph's Send API.
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
from app.core.langgraph.workflow.graph import WorkflowGraph
from app.core.langgraph.workflow.templates import workflow_template_registry
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.session import Session
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
)

router = APIRouter()
workflow_graph = WorkflowGraph()


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat"][0])
async def workflow_chat(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
    template: str = Query(default=None, description="Workflow template name (e.g., 'code_review', 'research_report')"),
):
    """Execute a multi-step workflow.

    Args:
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing messages.
        session: The current session from the auth token.
        template: Optional workflow template name.

    Returns:
        ChatResponse: The workflow execution results.
    """
    try:
        logger.info(
            "workflow_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
            template=template,
        )

        result = await workflow_graph.get_response(
            chat_request.messages,
            session.id,
            user_id=session.user_id,
            template_name=template,
        )

        logger.info("workflow_request_processed", session_id=session.id)
        return ChatResponse(messages=result)

    except Exception as e:
        logger.exception("workflow_request_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["chat_stream"][0])
async def workflow_chat_stream(
    request: Request,
    chat_request: ChatRequest,
    session: Session = Depends(get_current_session),
    template: str = Query(default=None, description="Workflow template name"),
):
    """Execute a multi-step workflow with streaming response.

    Args:
        request: The FastAPI request object for rate limiting.
        chat_request: The chat request containing messages.
        session: The current session from the auth token.
        template: Optional workflow template name.

    Returns:
        StreamingResponse: SSE stream of workflow execution.
    """
    try:
        logger.info(
            "workflow_stream_request_received",
            session_id=session.id,
            message_count=len(chat_request.messages),
            template=template,
        )

        stream = workflow_graph.get_stream_response(
            chat_request.messages,
            session.id,
            user_id=session.user_id,
            template_name=template,
        )

        return StreamingResponse(
            sse_event_generator(stream, session.id, log_event_name="workflow_stream_failed"),
            media_type="text/event-stream",
        )

    except Exception as e:
        logger.exception("workflow_stream_request_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates")
@limiter.limit("30/minute")
async def list_workflow_templates(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """List all available workflow templates.

    Returns:
        dict: List of available templates with names and descriptions.
    """
    templates = workflow_template_registry.list_templates()
    return {"templates": templates}
