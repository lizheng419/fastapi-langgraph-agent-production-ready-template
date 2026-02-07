"""Approval API endpoints for Human-in-the-Loop workflows.

Provides endpoints for listing, approving, and rejecting
pending approval requests from agent execution.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from app.api.v1.auth import get_current_session
from app.core.langgraph.hitl import approval_manager
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.session import Session
from app.schemas.approval import (
    ApprovalActionRequest,
    ApprovalListResponse,
    ApprovalRequestResponse,
)

router = APIRouter()


@router.get("/pending", response_model=ApprovalListResponse)
@limiter.limit("50 per minute")
async def list_pending_approvals(
    request: Request,
    session: Session = Depends(get_current_session),
):
    """List all pending approval requests for the current session.

    Args:
        request: The FastAPI request object for rate limiting.
        session: The current session from the auth token.

    Returns:
        ApprovalListResponse: List of pending approval requests.
    """
    try:
        pending = approval_manager.get_pending_requests(session_id=session.id)
        return ApprovalListResponse(
            requests=[
                ApprovalRequestResponse(**req.model_dump()) for req in pending
            ],
            total=len(pending),
        )
    except Exception as e:
        logger.exception("list_pending_approvals_failed", session_id=session.id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{request_id}", response_model=ApprovalRequestResponse)
@limiter.limit("50 per minute")
async def get_approval_request(
    request: Request,
    request_id: str,
    session: Session = Depends(get_current_session),
):
    """Get a specific approval request by ID.

    Args:
        request: The FastAPI request object for rate limiting.
        request_id: The approval request ID.
        session: The current session from the auth token.

    Returns:
        ApprovalRequestResponse: The approval request details.
    """
    try:
        approval_req = approval_manager.get_request(request_id)
        if not approval_req:
            raise HTTPException(status_code=404, detail="Approval request not found")

        if approval_req.session_id != session.id:
            raise HTTPException(status_code=403, detail="Access denied")

        return ApprovalRequestResponse(**approval_req.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_approval_request_failed", request_id=request_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{request_id}/approve", response_model=ApprovalRequestResponse)
@limiter.limit("20 per minute")
async def approve_request(
    request: Request,
    request_id: str,
    body: ApprovalActionRequest = None,
    session: Session = Depends(get_current_session),
):
    """Approve a pending approval request.

    Args:
        request: The FastAPI request object for rate limiting.
        request_id: The approval request ID.
        body: Optional comment for the approval.
        session: The current session from the auth token.

    Returns:
        ApprovalRequestResponse: The updated approval request.
    """
    try:
        approval_req = approval_manager.get_request(request_id)
        if not approval_req:
            raise HTTPException(status_code=404, detail="Approval request not found")

        if approval_req.session_id != session.id:
            raise HTTPException(status_code=403, detail="Access denied")

        comment = body.comment if body else None
        updated = approval_manager.approve(request_id, comment=comment)

        logger.info(
            "approval_request_approved_via_api",
            request_id=request_id,
            session_id=session.id,
        )

        return ApprovalRequestResponse(**updated.model_dump())
    except HTTPException:
        raise
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("approve_request_failed", request_id=request_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{request_id}/reject", response_model=ApprovalRequestResponse)
@limiter.limit("20 per minute")
async def reject_request(
    request: Request,
    request_id: str,
    body: ApprovalActionRequest = None,
    session: Session = Depends(get_current_session),
):
    """Reject a pending approval request.

    Args:
        request: The FastAPI request object for rate limiting.
        request_id: The approval request ID.
        body: Optional comment for the rejection.
        session: The current session from the auth token.

    Returns:
        ApprovalRequestResponse: The updated approval request.
    """
    try:
        approval_req = approval_manager.get_request(request_id)
        if not approval_req:
            raise HTTPException(status_code=404, detail="Approval request not found")

        if approval_req.session_id != session.id:
            raise HTTPException(status_code=403, detail="Access denied")

        comment = body.comment if body else None
        updated = approval_manager.reject(request_id, comment=comment)

        logger.info(
            "approval_request_rejected_via_api",
            request_id=request_id,
            session_id=session.id,
        )

        return ApprovalRequestResponse(**updated.model_dump())
    except HTTPException:
        raise
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("reject_request_failed", request_id=request_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
