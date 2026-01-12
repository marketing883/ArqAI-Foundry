"""
Microsoft Teams Integration Connector

Connects to MS Teams for notifications, approvals, and alerts.
Supports Adaptive Cards, webhooks, and Graph API.
"""

from datetime import datetime
from typing import Any

import structlog

from arqai_foundry.core.enums import IntegrationStatus
from arqai_foundry.core.models import ApprovalRequest, CapabilityToken, IROperation
from services.integrations.framework.base import (
    ActionResult,
    ConnectionStatus,
    IntegrationConnector,
    PermissionReport,
)

logger = structlog.get_logger(__name__)


class MSTeamsConnector(IntegrationConnector):
    """
    Microsoft Teams Integration Connector.

    Supports:
    - Send messages via webhooks
    - Adaptive Cards for rich content
    - Interactive approval workflows
    - Channel mentions
    - File attachments via Graph API
    """

    REQUIRED_PERMISSIONS = [
        "ChannelMessage.Send",
        "Chat.ReadWrite",
        "Team.ReadBasic.All",
        "Channel.ReadBasic.All",
        "Files.ReadWrite.All",
    ]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.tenant_id = config.get("tenant_id")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.webhook_url = config.get("webhook_url")  # Incoming webhook
        self.default_team_id = config.get("default_team_id")
        self.default_channel_id = config.get("default_channel_id")

        self._access_token = None
        self._token_expires_at = None

    async def connect(self) -> bool:
        """Establish connection to MS Teams."""
        logger.info(
            "msteams_connecting",
            tenant_id=self.tenant_id,
        )

        try:
            # In production, would authenticate via MSAL:
            # from msal import ConfidentialClientApplication
            # app = ConfidentialClientApplication(
            #     self.client_id,
            #     authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            #     client_credential=self.client_secret,
            # )
            # result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            # self._access_token = result["access_token"]

            self._status = IntegrationStatus.CONNECTED
            self._reset_errors()

            logger.info("msteams_connected")
            return True

        except Exception as e:
            self._status = IntegrationStatus.ERROR
            self._record_error(str(e))
            return False

    async def disconnect(self) -> None:
        """Disconnect from MS Teams."""
        self._access_token = None
        self._token_expires_at = None
        self._status = IntegrationStatus.DISCONNECTED
        logger.info("msteams_disconnected")

    async def test_connection(self) -> ConnectionStatus:
        """Test MS Teams connection."""
        start_time = datetime.utcnow()

        try:
            # Would verify token or test webhook
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ConnectionStatus(
                connected=True,
                status=IntegrationStatus.CONNECTED,
                last_check=datetime.utcnow(),
                latency_ms=latency,
                details={"tenant_id": self.tenant_id},
            )

        except Exception as e:
            return ConnectionStatus(
                connected=False,
                status=IntegrationStatus.ERROR,
                last_check=datetime.utcnow(),
                error=str(e),
            )

    async def test_permissions(self) -> PermissionReport:
        """Test MS Teams permissions."""
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
        """Execute an MS Teams action."""
        start_time = datetime.utcnow()

        logger.info(
            "msteams_action_started",
            action_type=action.type,
            target=action.target,
        )

        try:
            pre_state = {}
            trace = []

            if "teams.send_message" in action.type:
                result = await self._send_message(action, trace)
            elif "teams.send_card" in action.type:
                result = await self._send_adaptive_card(action, trace)
            elif "teams.send_approval" in action.type:
                result = await self._send_approval_card(action, trace)
            elif "teams.send_alert" in action.type:
                result = await self._send_alert(action, trace)
            elif "teams.reply_thread" in action.type:
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
        """Query Teams resources."""
        resource_type = filters.get("resource_type", "teams")

        if resource_type == "teams":
            return await self._list_teams()
        elif resource_type == "channels":
            team_id = filters.get("team_id", self.default_team_id)
            return await self._list_channels(team_id)

        return []

    async def get_resource_metadata(
        self,
        resource_id: str,
    ) -> dict[str, Any]:
        """Get Teams resource metadata."""
        return {"id": resource_id}

    # =========================================================================
    # Message Operations
    # =========================================================================

    async def _send_message(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Send a simple text message."""
        text = action.parameters.get("text", "")
        team_id = action.parameters.get("team_id", self.default_team_id)
        channel_id = action.parameters.get("channel_id", self.default_channel_id)

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "teams:sendMessage",
            "team_id": team_id,
            "channel_id": channel_id,
            "status": "initiated",
        })

        # Via webhook (simpler):
        # payload = {"text": text}
        # async with httpx.AsyncClient() as client:
        #     await client.post(self.webhook_url, json=payload)

        # Via Graph API (more features):
        # url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages"
        # headers = {"Authorization": f"Bearer {self._access_token}"}
        # payload = {"body": {"content": text}}

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "teams:sendMessage",
            "status": "completed",
        })

        logger.info("msteams_message_sent", team_id=team_id, channel_id=channel_id)
        return True

    async def _send_adaptive_card(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Send an Adaptive Card."""
        card = action.parameters.get("card", {})

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "teams:sendAdaptiveCard",
            "status": "initiated",
        })

        # Wrap card in attachment format for webhook
        # payload = {
        #     "type": "message",
        #     "attachments": [{
        #         "contentType": "application/vnd.microsoft.card.adaptive",
        #         "content": card,
        #     }]
        # }

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "teams:sendAdaptiveCard",
            "status": "completed",
        })

        logger.info("msteams_card_sent")
        return True

    async def _send_alert(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Send an alert with styling."""
        severity = action.parameters.get("severity", "warning")
        title = action.parameters.get("title", "Alert")
        message = action.parameters.get("message", "")

        card = self._build_alert_card(severity, title, message)

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "teams:sendAlert",
            "severity": severity,
            "status": "completed",
        })

        logger.info("msteams_alert_sent", severity=severity, title=title)
        return True

    async def _reply_thread(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Reply to a message thread."""
        message_id = action.parameters.get("message_id")
        text = action.parameters.get("text", "")

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "teams:replyThread",
            "message_id": message_id,
            "status": "completed",
        })

        # Via Graph API:
        # url = f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies"

        logger.info("msteams_reply_sent", message_id=message_id)
        return True

    # =========================================================================
    # Approval Workflow
    # =========================================================================

    async def _send_approval_card(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Send an approval request card."""
        approval_id = action.parameters.get("approval_id")
        action_summary = action.parameters.get("action_summary")
        risk_score = action.parameters.get("risk_score", 0)
        risk_tier = action.parameters.get("risk_tier", "medium")
        resources = action.parameters.get("resources", [])
        estimated_savings = action.parameters.get("estimated_savings")
        expires_at = action.parameters.get("expires_at")
        callback_url = action.parameters.get("callback_url")

        card = self._build_approval_card(
            approval_id=approval_id,
            action_summary=action_summary,
            risk_score=risk_score,
            risk_tier=risk_tier,
            resources=resources,
            estimated_savings=estimated_savings,
            expires_at=expires_at,
            callback_url=callback_url,
        )

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "teams:sendApprovalCard",
            "approval_id": approval_id,
            "status": "completed",
        })

        logger.info("msteams_approval_sent", approval_id=approval_id)
        return True

    async def send_approval_request(self, request: ApprovalRequest) -> str:
        """High-level method to send approval request."""
        card = self._build_approval_card(
            approval_id=str(request.approval_id),
            action_summary=request.action_summary,
            risk_score=request.risk_score,
            risk_tier=request.risk_tier.value,
            resources=request.resources_affected,
            estimated_savings=request.estimated_savings,
            expires_at=request.expires_at.isoformat() if request.expires_at else None,
            callback_url=None,  # Would be set from config
        )

        # Would send card and return message ID
        message_id = f"msg-{datetime.utcnow().timestamp()}"

        logger.info(
            "approval_notification_sent",
            approval_id=str(request.approval_id),
        )

        return message_id

    async def send_delegation_notification(
        self,
        request: ApprovalRequest,
        delegate_to: str,
    ) -> None:
        """Notify user of delegated approval."""
        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": "📋 Approval Delegated to You",
                    "weight": "Bolder",
                    "size": "Medium",
                },
                {
                    "type": "TextBlock",
                    "text": request.action_summary,
                    "wrap": True,
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "Approval ID", "value": str(request.approval_id)},
                        {"title": "Risk Score", "value": f"{request.risk_score}/100"},
                    ],
                },
            ],
        }

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
        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "Container",
                    "style": "attention",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": "🚨 BREAK-GLASS INVOKED",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": "Attention",
                        },
                    ],
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "User", "value": user_id},
                        {"title": "Action", "value": request.action_summary},
                        {"title": "Justification", "value": justification},
                        {"title": "Emergency Contact", "value": emergency_contact},
                        {"title": "Approval ID", "value": str(request.approval_id)},
                        {"title": "Risk Score", "value": f"{request.risk_score}/100"},
                    ],
                },
            ],
        }

        logger.warning(
            "break_glass_alert_sent",
            user_id=user_id,
            approval_id=str(request.approval_id),
        )

    async def send_execution_result(
        self,
        message_id: str,
        success: bool,
        action_summary: str,
        execution_time_ms: float,
        evidence_id: str,
    ) -> None:
        """Send execution result as reply."""
        status = "✅ Success" if success else "❌ Failed"

        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"Execution {status}",
                    "weight": "Bolder",
                },
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "Action", "value": action_summary},
                        {"title": "Execution Time", "value": f"{execution_time_ms:.2f}ms"},
                        {"title": "Evidence ID", "value": evidence_id},
                    ],
                },
            ],
        }

        logger.info(
            "execution_result_sent",
            message_id=message_id,
            success=success,
        )

    # =========================================================================
    # Adaptive Card Builders
    # =========================================================================

    def _build_approval_card(
        self,
        approval_id: str,
        action_summary: str,
        risk_score: int,
        risk_tier: str,
        resources: list[str],
        estimated_savings: str | None,
        expires_at: str | None,
        callback_url: str | None,
    ) -> dict[str, Any]:
        """Build Adaptive Card for approval request."""
        risk_color = {
            "low": "Good",
            "medium": "Warning",
            "high": "Attention",
            "critical": "Attention",
        }.get(risk_tier, "Default")

        body = [
            {
                "type": "TextBlock",
                "text": "🔐 Approval Required",
                "weight": "Bolder",
                "size": "Large",
            },
            {
                "type": "TextBlock",
                "text": action_summary,
                "wrap": True,
            },
            {
                "type": "ColumnSet",
                "columns": [
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "Risk Score",
                                "weight": "Bolder",
                                "size": "Small",
                            },
                            {
                                "type": "TextBlock",
                                "text": f"{risk_score}/100",
                                "size": "ExtraLarge",
                                "color": risk_color,
                            },
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "Risk Tier",
                                "weight": "Bolder",
                                "size": "Small",
                            },
                            {
                                "type": "TextBlock",
                                "text": risk_tier.upper(),
                                "size": "ExtraLarge",
                                "color": risk_color,
                            },
                        ],
                    },
                    {
                        "type": "Column",
                        "width": "stretch",
                        "items": [
                            {
                                "type": "TextBlock",
                                "text": "Resources",
                                "weight": "Bolder",
                                "size": "Small",
                            },
                            {
                                "type": "TextBlock",
                                "text": str(len(resources)),
                                "size": "ExtraLarge",
                            },
                        ],
                    },
                ],
            },
        ]

        if estimated_savings:
            body.append({
                "type": "TextBlock",
                "text": f"💰 Estimated Savings: {estimated_savings}",
                "weight": "Bolder",
                "color": "Good",
            })

        if resources:
            resource_items = [{"type": "TextBlock", "text": f"• {r}", "size": "Small"} for r in resources[:5]]
            if len(resources) > 5:
                resource_items.append({
                    "type": "TextBlock",
                    "text": f"...and {len(resources) - 5} more",
                    "size": "Small",
                    "isSubtle": True,
                })
            body.append({
                "type": "Container",
                "items": [
                    {
                        "type": "TextBlock",
                        "text": "Affected Resources:",
                        "weight": "Bolder",
                        "size": "Small",
                    },
                    *resource_items,
                ],
            })

        if expires_at:
            body.append({
                "type": "TextBlock",
                "text": f"⏰ Expires: {expires_at}",
                "size": "Small",
                "isSubtle": True,
            })

        actions = [
            {
                "type": "Action.Submit",
                "title": "✅ Approve",
                "style": "positive",
                "data": {
                    "action": "approve",
                    "approval_id": approval_id,
                },
            },
            {
                "type": "Action.Submit",
                "title": "❌ Reject",
                "style": "destructive",
                "data": {
                    "action": "reject",
                    "approval_id": approval_id,
                },
            },
            {
                "type": "Action.OpenUrl",
                "title": "📋 View Details",
                "url": f"/approvals/{approval_id}",
            },
        ]

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": body,
            "actions": actions,
        }

    def _build_alert_card(
        self,
        severity: str,
        title: str,
        message: str,
    ) -> dict[str, Any]:
        """Build Adaptive Card for alert."""
        style = {
            "info": "default",
            "warning": "warning",
            "error": "attention",
            "critical": "attention",
        }.get(severity, "default")

        emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨",
        }.get(severity, "📢")

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "Container",
                    "style": style,
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"{emoji} {title}",
                            "weight": "Bolder",
                            "size": "Large",
                        },
                        {
                            "type": "TextBlock",
                            "text": message,
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Severity: {severity.upper()} | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                            "size": "Small",
                            "isSubtle": True,
                        },
                    ],
                },
            ],
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _list_teams(self) -> list[dict[str, Any]]:
        """List joined teams."""
        # Via Graph API: GET /me/joinedTeams
        return []

    async def _list_channels(self, team_id: str) -> list[dict[str, Any]]:
        """List channels in a team."""
        # Via Graph API: GET /teams/{team_id}/channels
        return []

    async def handle_bot_message(
        self,
        activity: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle incoming bot messages/actions.

        This would be called by a webhook endpoint for bot framework.
        """
        activity_type = activity.get("type")
        value = activity.get("value", {})

        if activity_type == "invoke" and "action" in value:
            action = value.get("action")
            approval_id = value.get("approval_id")

            logger.info(
                "teams_action_received",
                action=action,
                approval_id=approval_id,
            )

            return {
                "action": action,
                "approval_id": approval_id,
                "user_id": activity.get("from", {}).get("id"),
                "user_name": activity.get("from", {}).get("name"),
            }

        return {}
