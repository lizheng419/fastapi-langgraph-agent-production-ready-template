"""Schemas for Human-in-the-Loop approval endpoints."""

from datetime import datetime
from typing import (
    Dict,
    List,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)


class ApprovalActionRequest(BaseModel):
    """Request body for approving or rejecting an action."""

    comment: Optional[str] = Field(default=None, description="Optional reviewer comment")


class ApprovalRequestResponse(BaseModel):
    """Response model for a single approval request."""

    id: str
    session_id: str
    user_id: Optional[str] = None
    action_type: str
    action_description: str
    action_data: Dict = Field(default_factory=dict)
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    reviewer_comment: Optional[str] = None
    expires_at: datetime


class ApprovalListResponse(BaseModel):
    """Response model for listing approval requests."""

    requests: List[ApprovalRequestResponse]
    total: int
