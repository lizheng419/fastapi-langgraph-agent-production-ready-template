"""API v1 router configuration.

This module sets up the main API router and includes all sub-routers for different
endpoints like authentication and chatbot functionality.
"""

from fastapi import APIRouter

from app.api.v1.approval import router as approval_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chatbot_v1 import router as chatbot_v1_router
from app.api.v1.chatbot_workflow import router as workflow_router
from app.api.v1.rag import router as rag_router
from app.core.logging import logger

api_router = APIRouter()

# Include routers
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(chatbot_v1_router, prefix="/chatbot", tags=["chatbot"])
api_router.include_router(workflow_router, prefix="/chatbot/workflow", tags=["workflow"])
api_router.include_router(approval_router, prefix="/approvals", tags=["approvals"])
api_router.include_router(rag_router, prefix="/rag", tags=["rag"])


@api_router.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Health status information.
    """
    logger.info("health_check_called")
    return {"status": "healthy", "version": "1.0.0"}
