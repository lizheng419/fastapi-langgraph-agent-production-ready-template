"""Approval manager for Human-in-the-Loop workflows.

Manages approval requests that pause agent execution until
a human reviewer approves or rejects the pending action.
"""

import asyncio
import uuid
from datetime import (
    datetime,
    timedelta,
)
from enum import Enum
from typing import (
    Dict,
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

from app.core.logging import logger


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    """A human approval request created during agent execution.

    Attributes:
        id: Unique identifier for this approval request.
        session_id: The session this request belongs to.
        user_id: The user who initiated the action.
        action_type: The type of action requiring approval.
        action_description: Human-readable description of the pending action.
        action_data: The data/parameters of the action.
        status: Current approval status.
        created_at: When the request was created.
        resolved_at: When the request was approved/rejected.
        reviewer_comment: Optional comment from the reviewer.
        expires_at: When the request expires if not acted upon.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = Field(..., description="Session ID")
    user_id: Optional[str] = Field(default=None, description="User ID")
    action_type: str = Field(..., description="Type of action (e.g., 'tool_execution', 'data_modification')")
    action_description: str = Field(..., description="Human-readable description")
    action_data: Dict = Field(default_factory=dict, description="Action parameters")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = Field(default=None)
    reviewer_comment: Optional[str] = Field(default=None)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(hours=1))


class ApprovalManager:
    """Manages human approval requests for agent actions.

    Provides in-memory storage and resolution of approval requests.
    In production, this should be backed by a database.
    """

    def __init__(self):
        """Initialize the approval manager."""
        self._requests: Dict[str, ApprovalRequest] = {}
        self._events: Dict[str, asyncio.Event] = {}

    async def create_request(
        self,
        session_id: str,
        action_type: str,
        action_description: str,
        action_data: Optional[Dict] = None,
        user_id: Optional[str] = None,
        timeout_hours: float = 1.0,
    ) -> ApprovalRequest:
        """Create a new approval request and wait for resolution.

        Args:
            session_id: The session ID.
            action_type: Type of action requiring approval.
            action_description: Human-readable description.
            action_data: Optional action parameters.
            user_id: Optional user ID.
            timeout_hours: Hours until the request expires.

        Returns:
            ApprovalRequest: The created approval request.
        """
        request = ApprovalRequest(
            session_id=session_id,
            user_id=user_id,
            action_type=action_type,
            action_description=action_description,
            action_data=action_data or {},
            expires_at=datetime.utcnow() + timedelta(hours=timeout_hours),
        )

        self._requests[request.id] = request
        self._events[request.id] = asyncio.Event()

        logger.info(
            "approval_request_created",
            request_id=request.id,
            session_id=session_id,
            action_type=action_type,
        )

        return request

    async def wait_for_approval(self, request_id: str, timeout: float = 3600) -> ApprovalRequest:
        """Wait for an approval request to be resolved.

        Args:
            request_id: The approval request ID.
            timeout: Maximum seconds to wait.

        Returns:
            ApprovalRequest: The resolved request.

        Raises:
            TimeoutError: If the request is not resolved within the timeout.
            KeyError: If the request ID is not found.
        """
        if request_id not in self._events:
            raise KeyError(f"Approval request '{request_id}' not found")

        event = self._events[request_id]

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            # Mark as expired
            request = self._requests[request_id]
            request.status = ApprovalStatus.EXPIRED
            request.resolved_at = datetime.utcnow()
            logger.warning("approval_request_expired", request_id=request_id)
            raise TimeoutError(f"Approval request '{request_id}' expired")

        return self._requests[request_id]

    def approve(self, request_id: str, comment: Optional[str] = None) -> ApprovalRequest:
        """Approve a pending request.

        Args:
            request_id: The approval request ID.
            comment: Optional reviewer comment.

        Returns:
            ApprovalRequest: The updated request.

        Raises:
            KeyError: If the request is not found.
            ValueError: If the request is not in PENDING status.
        """
        request = self._requests.get(request_id)
        if not request:
            raise KeyError(f"Approval request '{request_id}' not found")

        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request '{request_id}' is already {request.status.value}")

        request.status = ApprovalStatus.APPROVED
        request.resolved_at = datetime.utcnow()
        request.reviewer_comment = comment

        # Signal the waiting coroutine
        if request_id in self._events:
            self._events[request_id].set()

        logger.info(
            "approval_request_approved",
            request_id=request_id,
            comment=comment,
        )

        return request

    def reject(self, request_id: str, comment: Optional[str] = None) -> ApprovalRequest:
        """Reject a pending request.

        Args:
            request_id: The approval request ID.
            comment: Optional reviewer comment.

        Returns:
            ApprovalRequest: The updated request.

        Raises:
            KeyError: If the request is not found.
            ValueError: If the request is not in PENDING status.
        """
        request = self._requests.get(request_id)
        if not request:
            raise KeyError(f"Approval request '{request_id}' not found")

        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request '{request_id}' is already {request.status.value}")

        request.status = ApprovalStatus.REJECTED
        request.resolved_at = datetime.utcnow()
        request.reviewer_comment = comment

        # Signal the waiting coroutine
        if request_id in self._events:
            self._events[request_id].set()

        logger.info(
            "approval_request_rejected",
            request_id=request_id,
            comment=comment,
        )

        return request

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get a specific approval request.

        Args:
            request_id: The approval request ID.

        Returns:
            Optional[ApprovalRequest]: The request if found.
        """
        return self._requests.get(request_id)

    def get_pending_requests(self, session_id: Optional[str] = None) -> List[ApprovalRequest]:
        """Get all pending approval requests, optionally filtered by session.

        Args:
            session_id: Optional session ID to filter by.

        Returns:
            List[ApprovalRequest]: List of pending requests.
        """
        now = datetime.utcnow()
        pending = []
        for req in self._requests.values():
            if req.status != ApprovalStatus.PENDING:
                continue
            # Auto-expire stale requests
            if req.expires_at < now:
                req.status = ApprovalStatus.EXPIRED
                req.resolved_at = now
                continue
            if session_id and req.session_id != session_id:
                continue
            pending.append(req)
        return pending

    def cleanup_expired(self) -> int:
        """Clean up expired requests.

        Returns:
            int: Number of requests cleaned up.
        """
        now = datetime.utcnow()
        expired_ids = []
        for req_id, req in self._requests.items():
            if req.status == ApprovalStatus.PENDING and req.expires_at < now:
                req.status = ApprovalStatus.EXPIRED
                req.resolved_at = now
                expired_ids.append(req_id)

        for req_id in expired_ids:
            if req_id in self._events:
                self._events[req_id].set()

        if expired_ids:
            logger.info("approval_requests_expired", count=len(expired_ids))

        return len(expired_ids)


# Global approval manager instance
approval_manager = ApprovalManager()
