"""Unit tests for the HITL ApprovalManager."""

import asyncio

import pytest

from app.core.langgraph.hitl.manager import (
    ApprovalManager,
    ApprovalStatus,
)


class TestApprovalManagerCreate:
    """Tests for creating approval requests."""

    def setup_method(self):
        """Create a fresh ApprovalManager for each test."""
        self.manager = ApprovalManager()

    @pytest.mark.asyncio
    async def test_create_request(self):
        """Test creating an approval request."""
        request = await self.manager.create_request(
            session_id="sess_1",
            action_type="tool_execution",
            action_description="Delete all records",
            action_data={"table": "users"},
            user_id="user_1",
        )
        assert request.session_id == "sess_1"
        assert request.action_type == "tool_execution"
        assert request.action_description == "Delete all records"
        assert request.action_data == {"table": "users"}
        assert request.user_id == "user_1"
        assert request.status == ApprovalStatus.PENDING
        assert request.id is not None
        assert request.resolved_at is None

    @pytest.mark.asyncio
    async def test_create_multiple_requests(self):
        """Test creating multiple requests yields unique IDs."""
        r1 = await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="Delete A"
        )
        r2 = await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="Delete B"
        )
        assert r1.id != r2.id


class TestApprovalManagerApproveReject:
    """Tests for approving and rejecting requests."""

    def setup_method(self):
        """Create a fresh ApprovalManager for each test."""
        self.manager = ApprovalManager()

    @pytest.mark.asyncio
    async def test_approve_request(self):
        """Test approving a pending request."""
        request = await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="Delete record"
        )
        approved = self.manager.approve(request.id, comment="Looks good")
        assert approved.status == ApprovalStatus.APPROVED
        assert approved.reviewer_comment == "Looks good"
        assert approved.resolved_at is not None

    @pytest.mark.asyncio
    async def test_reject_request(self):
        """Test rejecting a pending request."""
        request = await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="Delete record"
        )
        rejected = self.manager.reject(request.id, comment="Too risky")
        assert rejected.status == ApprovalStatus.REJECTED
        assert rejected.reviewer_comment == "Too risky"
        assert rejected.resolved_at is not None

    @pytest.mark.asyncio
    async def test_approve_already_approved_raises(self):
        """Test that approving an already-approved request raises ValueError."""
        request = await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="Delete"
        )
        self.manager.approve(request.id)
        with pytest.raises(ValueError, match="already"):
            self.manager.approve(request.id)

    @pytest.mark.asyncio
    async def test_reject_already_rejected_raises(self):
        """Test that rejecting an already-rejected request raises ValueError."""
        request = await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="Delete"
        )
        self.manager.reject(request.id)
        with pytest.raises(ValueError, match="already"):
            self.manager.reject(request.id)

    @pytest.mark.asyncio
    async def test_approve_nonexistent_raises(self):
        """Test that approving nonexistent request raises KeyError."""
        with pytest.raises(KeyError):
            self.manager.approve("nonexistent_id")

    @pytest.mark.asyncio
    async def test_reject_nonexistent_raises(self):
        """Test that rejecting nonexistent request raises KeyError."""
        with pytest.raises(KeyError):
            self.manager.reject("nonexistent_id")


class TestApprovalManagerQuery:
    """Tests for querying approval requests."""

    def setup_method(self):
        """Create a fresh ApprovalManager for each test."""
        self.manager = ApprovalManager()

    @pytest.mark.asyncio
    async def test_get_request(self):
        """Test retrieving a specific request."""
        request = await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="Delete"
        )
        fetched = self.manager.get_request(request.id)
        assert fetched is not None
        assert fetched.id == request.id

    def test_get_nonexistent_request(self):
        """Test retrieving nonexistent request returns None."""
        assert self.manager.get_request("nope") is None

    @pytest.mark.asyncio
    async def test_get_pending_requests(self):
        """Test listing pending requests."""
        await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="A"
        )
        await self.manager.create_request(
            session_id="s2", action_type="modify", action_description="B"
        )
        pending = self.manager.get_pending_requests()
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_get_pending_requests_filtered_by_session(self):
        """Test listing pending requests filtered by session."""
        await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="A"
        )
        await self.manager.create_request(
            session_id="s2", action_type="modify", action_description="B"
        )
        pending = self.manager.get_pending_requests(session_id="s1")
        assert len(pending) == 1
        assert pending[0].session_id == "s1"

    @pytest.mark.asyncio
    async def test_approved_not_in_pending(self):
        """Test that approved requests don't appear in pending list."""
        r1 = await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="A"
        )
        await self.manager.create_request(
            session_id="s1", action_type="modify", action_description="B"
        )
        self.manager.approve(r1.id)
        pending = self.manager.get_pending_requests()
        assert len(pending) == 1


class TestApprovalManagerWait:
    """Tests for wait_for_approval async flow."""

    def setup_method(self):
        """Create a fresh ApprovalManager for each test."""
        self.manager = ApprovalManager()

    @pytest.mark.asyncio
    async def test_wait_and_approve(self):
        """Test that wait_for_approval resolves when approved."""
        request = await self.manager.create_request(
            session_id="s1", action_type="delete", action_description="Delete"
        )

        async def approve_after_delay():
            await asyncio.sleep(0.05)
            self.manager.approve(request.id, comment="OK")

        asyncio.create_task(approve_after_delay())
        resolved = await self.manager.wait_for_approval(request.id, timeout=2)
        assert resolved.status == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_wait_nonexistent_raises(self):
        """Test that waiting for nonexistent request raises KeyError."""
        with pytest.raises(KeyError):
            await self.manager.wait_for_approval("nope", timeout=1)
