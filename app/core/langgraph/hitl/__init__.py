"""Human-in-the-Loop (HITL) module for approval workflows.

Provides interrupt-based approval mechanisms for sensitive agent actions,
allowing human review before execution of critical operations.
"""

from app.core.langgraph.hitl.manager import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalStatus,
    approval_manager,
)

__all__ = [
    "ApprovalManager",
    "ApprovalRequest",
    "ApprovalStatus",
    "approval_manager",
]
