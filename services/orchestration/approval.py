"""
Approval Workflow Service

Handles human-in-the-loop approvals for medium/high-risk actions.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import structlog

from arqai_foundry.core.enums import ApprovalStatus, RiskTier
from arqai_foundry.core.exceptions import ApprovalTimeoutError, OrchestrationError
from arqai_foundry.core.models import ApprovalRequest

logger = structlog.get_logger(__name__)


class ApprovalWorkflowService:
    """
    Manages approval workflows for high-risk actions.

    Features:
    - Multi-approver support
    - Timeout handling
    - Delegation
    - Emergency break-glass
    - Notification integration (Slack, Teams)
    """

    def __init__(self):
        # Pending approvals
        self._approvals: dict[UUID, ApprovalRequest] = {}

        # Notification handlers
        self._notification_handlers: dict[str, Any] = {}

    async def create_approval_request(
        self,
        execution_id: UUID,
        action_summary: str,
        risk_score: int,
        risk_tier: RiskTier,
        required_approvers: list[dict[str, str]],
        resources_affected: list[str],
        estimated_savings: str | None = None,
        timeout_hours: int = 24,
        delegation_allowed: bool = False,
    ) -> ApprovalRequest:
        """Create a new approval request."""
        approval_id = uuid4()
        expires_at = datetime.utcnow() + timedelta(hours=timeout_hours)

        request = ApprovalRequest(
            approval_id=approval_id,
            execution_id=execution_id,
            action_summary=action_summary,
            risk_score=risk_score,
            risk_tier=risk_tier,
            required_approvers=required_approvers,
            timeout_hours=timeout_hours,
            delegation_allowed=delegation_allowed,
            resources_affected=resources_affected,
            estimated_savings=estimated_savings,
            expires_at=expires_at,
        )

        self._approvals[approval_id] = request

        logger.info(
            "approval_request_created",
            approval_id=str(approval_id),
            execution_id=str(execution_id),
            risk_tier=risk_tier.value,
            approvers=[a.get("role") for a in required_approvers],
        )

        # Send notifications
        await self._send_notifications(request)

        return request

    async def approve(
        self,
        approval_id: UUID,
        approved_by: str,
        approver_role: str,
        comments: str | None = None,
    ) -> ApprovalRequest:
        """Approve a request."""
        request = self._approvals.get(approval_id)

        if not request:
            raise OrchestrationError(f"Approval request not found: {approval_id}")

        if request.status != ApprovalStatus.PENDING:
            raise OrchestrationError(
                f"Request is not pending: {request.status}"
            )

        if datetime.utcnow() > request.expires_at:
            request.status = ApprovalStatus.EXPIRED
            raise ApprovalTimeoutError(
                f"Approval request has expired",
                details={"approval_id": str(approval_id)},
            )

        # Verify approver is authorized
        if not self._is_authorized_approver(request, approver_role):
            raise OrchestrationError(
                f"User role '{approver_role}' is not authorized to approve"
            )

        request.status = ApprovalStatus.APPROVED
        request.approved_by = approved_by
        request.resolved_at = datetime.utcnow()

        logger.info(
            "approval_granted",
            approval_id=str(approval_id),
            approved_by=approved_by,
            approver_role=approver_role,
        )

        return request

    async def reject(
        self,
        approval_id: UUID,
        rejected_by: str,
        reason: str,
    ) -> ApprovalRequest:
        """Reject a request."""
        request = self._approvals.get(approval_id)

        if not request:
            raise OrchestrationError(f"Approval request not found: {approval_id}")

        if request.status != ApprovalStatus.PENDING:
            raise OrchestrationError(
                f"Request is not pending: {request.status}"
            )

        request.status = ApprovalStatus.REJECTED
        request.rejected_by = rejected_by
        request.rejection_reason = reason
        request.resolved_at = datetime.utcnow()

        logger.info(
            "approval_rejected",
            approval_id=str(approval_id),
            rejected_by=rejected_by,
            reason=reason,
        )

        return request

    async def delegate(
        self,
        approval_id: UUID,
        delegated_by: str,
        delegate_to: str,
        delegate_role: str,
    ) -> ApprovalRequest:
        """Delegate approval to another user."""
        request = self._approvals.get(approval_id)

        if not request:
            raise OrchestrationError(f"Approval request not found: {approval_id}")

        if not request.delegation_allowed:
            raise OrchestrationError("Delegation is not allowed for this request")

        if request.status != ApprovalStatus.PENDING:
            raise OrchestrationError(
                f"Request is not pending: {request.status}"
            )

        # Add delegate to approvers
        request.required_approvers.append({
            "role": delegate_role,
            "user_id": delegate_to,
            "delegated_by": delegated_by,
        })

        logger.info(
            "approval_delegated",
            approval_id=str(approval_id),
            delegated_by=delegated_by,
            delegate_to=delegate_to,
        )

        # Send notification to delegate
        await self._send_delegation_notification(request, delegate_to)

        return request

    async def break_glass(
        self,
        approval_id: UUID,
        user_id: str,
        justification: str,
        emergency_contact: str,
    ) -> ApprovalRequest:
        """
        Emergency break-glass override.

        This bypasses normal approval but:
        - Requires justification
        - Notifies exec team immediately
        - Creates special audit evidence
        """
        request = self._approvals.get(approval_id)

        if not request:
            raise OrchestrationError(f"Approval request not found: {approval_id}")

        logger.warning(
            "break_glass_invoked",
            approval_id=str(approval_id),
            user_id=user_id,
            justification=justification,
        )

        # Notify exec team
        await self._notify_break_glass(
            request=request,
            user_id=user_id,
            justification=justification,
            emergency_contact=emergency_contact,
        )

        request.status = ApprovalStatus.APPROVED
        request.approved_by = f"BREAK_GLASS:{user_id}"
        request.resolved_at = datetime.utcnow()

        return request

    async def get_approval(self, approval_id: UUID) -> ApprovalRequest | None:
        """Get an approval request."""
        return self._approvals.get(approval_id)

    async def get_pending_approvals(
        self,
        approver_role: str | None = None,
    ) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        pending = [
            r for r in self._approvals.values()
            if r.status == ApprovalStatus.PENDING
        ]

        if approver_role:
            pending = [
                r for r in pending
                if self._is_authorized_approver(r, approver_role)
            ]

        # Check for expired requests
        now = datetime.utcnow()
        for request in pending:
            if now > request.expires_at:
                request.status = ApprovalStatus.EXPIRED

        return [r for r in pending if r.status == ApprovalStatus.PENDING]

    async def check_expired(self) -> int:
        """Check and mark expired requests."""
        now = datetime.utcnow()
        expired_count = 0

        for request in self._approvals.values():
            if request.status == ApprovalStatus.PENDING and now > request.expires_at:
                request.status = ApprovalStatus.EXPIRED
                expired_count += 1

                logger.warning(
                    "approval_expired",
                    approval_id=str(request.approval_id),
                )

        return expired_count

    def _is_authorized_approver(
        self,
        request: ApprovalRequest,
        approver_role: str,
    ) -> bool:
        """Check if a role is authorized to approve."""
        for approver in request.required_approvers:
            if approver.get("role") == approver_role:
                return True
        return False

    # =========================================================================
    # Notification Handlers
    # =========================================================================

    def register_notification_handler(
        self,
        channel: str,
        handler: Any,
    ) -> None:
        """Register a notification handler."""
        self._notification_handlers[channel] = handler
        logger.info("notification_handler_registered", channel=channel)

    async def _send_notifications(self, request: ApprovalRequest) -> None:
        """Send notifications for a new approval request."""
        for channel, handler in self._notification_handlers.items():
            try:
                await handler.send_approval_request(request)
            except Exception as e:
                logger.error(
                    "notification_failed",
                    channel=channel,
                    error=str(e),
                )

    async def _send_delegation_notification(
        self,
        request: ApprovalRequest,
        delegate_to: str,
    ) -> None:
        """Send notification for delegation."""
        for channel, handler in self._notification_handlers.items():
            try:
                await handler.send_delegation_notification(request, delegate_to)
            except Exception as e:
                logger.error(
                    "delegation_notification_failed",
                    channel=channel,
                    error=str(e),
                )

    async def _notify_break_glass(
        self,
        request: ApprovalRequest,
        user_id: str,
        justification: str,
        emergency_contact: str,
    ) -> None:
        """Send break-glass notifications to exec team."""
        for channel, handler in self._notification_handlers.items():
            try:
                await handler.send_break_glass_alert(
                    request=request,
                    user_id=user_id,
                    justification=justification,
                    emergency_contact=emergency_contact,
                )
            except Exception as e:
                logger.error(
                    "break_glass_notification_failed",
                    channel=channel,
                    error=str(e),
                )
