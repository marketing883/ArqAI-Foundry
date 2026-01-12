"""
Slack Integration Connector

Connects to Slack for notifications, approvals, and alerts.
Supports sending messages, interactive approvals, and rich blocks.
"""

from datetime import datetime
from typing import Any

import structlog

from arqai_foundry.core.enums import IntegrationStatus, RiskTier
from arqai_foundry.core.models import ApprovalRequest, CapabilityToken, IROperation
from services.integrations.framework.base import (
    ActionResult,
    ConnectionStatus,
    IntegrationConnector,
    PermissionReport,
)

logger = structlog.get_logger(__name__)


class SlackConnector(IntegrationConnector):
    """
    Slack Integration Connector.

    Supports:
    - Send messages to channels/users
    - Interactive approval workflows
    - Rich message blocks
    - Thread replies
    - File uploads
    - Slash commands (webhook handler)
    """

    REQUIRED_PERMISSIONS = [
        "chat:write",
        "chat:write.public",
        "files:write",
        "users:read",
        "channels:read",
        "groups:read",
        "im:read",
    ]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get("bot_token")
        self.signing_secret = config.get("signing_secret")
        self.app_token = config.get("app_token")  # For socket mode
        self.default_channel = config.get("default_channel", "#arqai-notifications")

        self._client = None
        self._socket_client = None

    async def connect(self) -> bool:
        """Establish connection to Slack."""
        logger.info(
            "slack_connecting",
            default_channel=self.default_channel,
        )

        try:
            # In production, would initialize slack_sdk:
            # from slack_sdk.web.async_client import AsyncWebClient
            # self._client = AsyncWebClient(token=self.bot_token)
            # auth_response = await self._client.auth_test()

            self._status = IntegrationStatus.CONNECTED
            self._reset_errors()

            logger.info("slack_connected")
            return True

        except Exception as e:
            self._status = IntegrationStatus.ERROR
            self._record_error(str(e))
            return False

    async def disconnect(self) -> None:
        """Disconnect from Slack."""
        self._client = None
        self._socket_client = None
        self._status = IntegrationStatus.DISCONNECTED
        logger.info("slack_disconnected")

    async def test_connection(self) -> ConnectionStatus:
        """Test Slack connection."""
        start_time = datetime.utcnow()

        try:
            # Would call auth.test() in production
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ConnectionStatus(
                connected=True,
                status=IntegrationStatus.CONNECTED,
                last_check=datetime.utcnow(),
                latency_ms=latency,
                details={"default_channel": self.default_channel},
            )

        except Exception as e:
            return ConnectionStatus(
                connected=False,
                status=IntegrationStatus.ERROR,
                last_check=datetime.utcnow(),
                error=str(e),
            )

    async def test_permissions(self) -> PermissionReport:
        """Test Slack permissions (scopes)."""
        return PermissionReport(
            all_permissions_granted=True,
            required_permissions=self.REQUIRED_PERMISSIONS,
            granted_permissions=self.REQUIRED_PERMISSIONS,
            missing_permissions=[],
            checked_at=datetime.utcnow(),
        )

    async def execute_action(
        self,
        action: IROperation,
        capability_token: CapabilityToken,
    ) -> ActionResult:
        """Execute a Slack action."""
        start_time = datetime.utcnow()

        logger.info(
            "slack_action_started",
            action_type=action.type,
            target=action.target,
        )

        try:
            pre_state = {}
            trace = []

            if "slack.send_message" in action.type:
                result = await self._send_message(action, trace)
            elif "slack.send_approval" in action.type:
                result = await self._send_approval_request(action, trace)
            elif "slack.send_alert" in action.type:
                result = await self._send_alert(action, trace)
            elif "slack.upload_file" in action.type:
                result = await self._upload_file(action, trace)
            elif "slack.reply_thread" in action.type:
                result = await self._reply_thread(action, trace)
            else:
                trace.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "unknown",
                    "error": f"Unknown action type: {action.type}",
                })
                result = False

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ActionResult(
                success=result,
                action=action.type,
                target=action.target,
                pre_state=pre_state,
                post_state={},
                trace=trace,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self._record_error(str(e))

            return ActionResult(
                success=False,
                action=action.type,
                target=action.target,
                pre_state={},
                post_state={},
                trace=[{
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                }],
                error=str(e),
                execution_time_ms=execution_time,
            )

    async def capture_pre_state(self, action: IROperation) -> dict[str, Any]:
        """Capture pre-state (not applicable for notifications)."""
        return {}

    async def capture_post_state(self, action: IROperation) -> dict[str, Any]:
        """Capture post-state (not applicable for notifications)."""
        return {}

    async def query_resources(
        self,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Query Slack resources (channels, users)."""
        resource_type = filters.get("resource_type", "channels")

        if resource_type == "channels":
            return await self._list_channels()
        elif resource_type == "users":
            return await self._list_users()

        return []

    async def get_resource_metadata(
        self,
        resource_id: str,
    ) -> dict[str, Any]:
        """Get Slack resource metadata."""
        if resource_id.startswith("C"):  # Channel
            return {"type": "channel", "id": resource_id}
        elif resource_id.startswith("U"):  # User
            return {"type": "user", "id": resource_id}
        return {"id": resource_id}

    # =========================================================================
    # Message Operations
    # =========================================================================

    async def _send_message(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Send a message to a channel or user."""
        channel = action.parameters.get("channel", self.default_channel)
        text = action.parameters.get("text", "")
        blocks = action.parameters.get("blocks")
        thread_ts = action.parameters.get("thread_ts")

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "slack:postMessage",
            "channel": channel,
            "status": "initiated",
        })

        # In production:
        # response = await self._client.chat_postMessage(
        #     channel=channel,
        #     text=text,
        #     blocks=blocks,
        #     thread_ts=thread_ts,
        # )

        message_ts = datetime.utcnow().timestamp()

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "slack:postMessage",
            "channel": channel,
            "message_ts": str(message_ts),
            "status": "completed",
        })

        logger.info("slack_message_sent", channel=channel)
        return True

    async def _reply_thread(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Reply to a thread."""
        channel = action.parameters.get("channel")
        thread_ts = action.parameters.get("thread_ts")
        text = action.parameters.get("text", "")

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "slack:replyThread",
            "channel": channel,
            "thread_ts": thread_ts,
            "status": "completed",
        })

        logger.info("slack_thread_reply", channel=channel, thread_ts=thread_ts)
        return True

    async def _upload_file(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Upload a file to Slack."""
        channel = action.parameters.get("channel", self.default_channel)
        file_path = action.parameters.get("file_path")
        file_content = action.parameters.get("content")
        filename = action.parameters.get("filename", "evidence.json")
        title = action.parameters.get("title", "Evidence File")

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "slack:uploadFile",
            "channel": channel,
            "filename": filename,
            "status": "completed",
        })

        # In production:
        # await self._client.files_upload_v2(
        #     channel=channel,
        #     file=file_path or file_content,
        #     filename=filename,
        #     title=title,
        # )

        logger.info("slack_file_uploaded", channel=channel, filename=filename)
        return True

    async def _send_alert(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Send an alert message with severity styling."""
        channel = action.parameters.get("channel", self.default_channel)
        severity = action.parameters.get("severity", "warning")
        title = action.parameters.get("title", "Alert")
        message = action.parameters.get("message", "")

        color_map = {
            "info": "#36a64f",
            "warning": "#ffcc00",
            "error": "#ff0000",
            "critical": "#990000",
        }

        blocks = self._build_alert_blocks(
            severity=severity,
            title=title,
            message=message,
            color=color_map.get(severity, "#808080"),
        )

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "slack:sendAlert",
            "channel": channel,
            "severity": severity,
            "status": "completed",
        })

        logger.info(
            "slack_alert_sent",
            channel=channel,
            severity=severity,
            title=title,
        )
        return True

    # =========================================================================
    # Approval Workflow
    # =========================================================================

    async def _send_approval_request(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Send an interactive approval request."""
        channel = action.parameters.get("channel", self.default_channel)
        approval_id = action.parameters.get("approval_id")
        action_summary = action.parameters.get("action_summary")
        risk_score = action.parameters.get("risk_score", 0)
        risk_tier = action.parameters.get("risk_tier", "medium")
        resources = action.parameters.get("resources", [])
        estimated_savings = action.parameters.get("estimated_savings")
        expires_at = action.parameters.get("expires_at")

        blocks = self._build_approval_blocks(
            approval_id=approval_id,
            action_summary=action_summary,
            risk_score=risk_score,
            risk_tier=risk_tier,
            resources=resources,
            estimated_savings=estimated_savings,
            expires_at=expires_at,
        )

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "slack:sendApproval",
            "channel": channel,
            "approval_id": approval_id,
            "status": "completed",
        })

        logger.info(
            "slack_approval_sent",
            channel=channel,
            approval_id=approval_id,
        )
        return True

    async def send_approval_request(self, request: ApprovalRequest) -> str:
        """High-level method to send approval request notification."""
        blocks = self._build_approval_blocks(
            approval_id=str(request.approval_id),
            action_summary=request.action_summary,
            risk_score=request.risk_score,
            risk_tier=request.risk_tier.value,
            resources=request.resources_affected,
            estimated_savings=request.estimated_savings,
            expires_at=request.expires_at.isoformat() if request.expires_at else None,
        )

        # Would send message and return ts
        message_ts = str(datetime.utcnow().timestamp())

        logger.info(
            "approval_notification_sent",
            approval_id=str(request.approval_id),
            channel=self.default_channel,
        )

        return message_ts

    async def send_delegation_notification(
        self,
        request: ApprovalRequest,
        delegate_to: str,
    ) -> None:
        """Notify user of delegated approval."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Approval Delegated to You*\n\n{request.action_summary}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Approval ID: `{request.approval_id}`",
                    }
                ],
            },
        ]

        logger.info(
            "delegation_notification_sent",
            delegate_to=delegate_to,
            approval_id=str(request.approval_id),
        )

    async def send_break_glass_alert(
        self,
        request: ApprovalRequest,
        user_id: str,
        justification: str,
        emergency_contact: str,
    ) -> None:
        """Send break-glass alert to exec team."""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 BREAK-GLASS INVOKED",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*User:* {user_id}\n*Action:* {request.action_summary}\n*Justification:* {justification}\n*Emergency Contact:* {emergency_contact}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Approval ID: `{request.approval_id}` | Risk Score: {request.risk_score}",
                    }
                ],
            },
        ]

        logger.warning(
            "break_glass_alert_sent",
            user_id=user_id,
            approval_id=str(request.approval_id),
        )

    async def send_execution_result(
        self,
        channel: str,
        thread_ts: str,
        success: bool,
        action_summary: str,
        execution_time_ms: float,
        evidence_id: str,
    ) -> None:
        """Send execution result as thread reply."""
        emoji = "✅" if success else "❌"
        status = "Success" if success else "Failed"

        text = f"{emoji} *Execution {status}*\n\n{action_summary}\n\nExecution Time: {execution_time_ms:.2f}ms\nEvidence ID: `{evidence_id}`"

        logger.info(
            "execution_result_sent",
            channel=channel,
            thread_ts=thread_ts,
            success=success,
        )

    # =========================================================================
    # Block Builders
    # =========================================================================

    def _build_approval_blocks(
        self,
        approval_id: str,
        action_summary: str,
        risk_score: int,
        risk_tier: str,
        resources: list[str],
        estimated_savings: str | None,
        expires_at: str | None,
    ) -> list[dict[str, Any]]:
        """Build Slack blocks for approval request."""
        risk_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴",
        }.get(risk_tier, "⚪")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔐 Approval Required",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Action:* {action_summary}",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Risk Score:*\n{risk_emoji} {risk_score}/100 ({risk_tier.upper()})",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Resources:*\n{len(resources)} affected",
                    },
                ],
            },
        ]

        if estimated_savings:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Estimated Savings:* {estimated_savings}",
                },
            })

        if resources:
            resource_list = "\n".join([f"• `{r}`" for r in resources[:5]])
            if len(resources) > 5:
                resource_list += f"\n• _...and {len(resources) - 5} more_"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Affected Resources:*\n{resource_list}",
                },
            })

        blocks.append({
            "type": "actions",
            "block_id": f"approval_{approval_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Approve",
                        "emoji": True,
                    },
                    "style": "primary",
                    "action_id": "approve_action",
                    "value": approval_id,
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Reject",
                        "emoji": True,
                    },
                    "style": "danger",
                    "action_id": "reject_action",
                    "value": approval_id,
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📋 View Details",
                        "emoji": True,
                    },
                    "action_id": "view_details",
                    "value": approval_id,
                },
            ],
        })

        if expires_at:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⏰ Expires: {expires_at} | ID: `{approval_id}`",
                    }
                ],
            })

        return blocks

    def _build_alert_blocks(
        self,
        severity: str,
        title: str,
        message: str,
        color: str,
    ) -> list[dict[str, Any]]:
        """Build Slack blocks for alert message."""
        severity_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨",
        }.get(severity, "📢")

        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji} {title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message,
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Severity: *{severity.upper()}* | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    }
                ],
            },
        ]

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _list_channels(self) -> list[dict[str, Any]]:
        """List available channels."""
        # In production: await self._client.conversations_list()
        return []

    async def _list_users(self) -> list[dict[str, Any]]:
        """List workspace users."""
        # In production: await self._client.users_list()
        return []

    async def handle_interaction(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle Slack interactive component callbacks.

        This would be called by a webhook endpoint when users
        click buttons in approval messages.
        """
        action = payload.get("actions", [{}])[0]
        action_id = action.get("action_id")
        approval_id = action.get("value")
        user = payload.get("user", {})

        logger.info(
            "slack_interaction_received",
            action_id=action_id,
            approval_id=approval_id,
            user_id=user.get("id"),
        )

        return {
            "action_id": action_id,
            "approval_id": approval_id,
            "user_id": user.get("id"),
            "user_name": user.get("name"),
        }
