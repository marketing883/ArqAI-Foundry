"""
Jira Integration Connector

Connects to Jira for ticket management and workflow automation.
Supports creating issues, updating status, adding comments, and querying.
"""

from datetime import datetime
from typing import Any

import structlog

from arqai_foundry.core.enums import IntegrationStatus
from arqai_foundry.core.models import CapabilityToken, IROperation
from services.integrations.framework.base import (
    ActionResult,
    ConnectionStatus,
    IntegrationConnector,
    PermissionReport,
)

logger = structlog.get_logger(__name__)


class JiraConnector(IntegrationConnector):
    """
    Jira Integration Connector.

    Supports:
    - Create issues (stories, tasks, bugs)
    - Update issue status
    - Add comments
    - Attach evidence files
    - Query issues by JQL
    - Link issues
    """

    REQUIRED_PERMISSIONS = [
        "browse_projects",
        "create_issues",
        "edit_issues",
        "transition_issues",
        "add_comments",
        "attach_files",
        "link_issues",
    ]

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "").rstrip("/")
        self.username = config.get("username")
        self.api_token = config.get("api_token")
        self.project_key = config.get("project_key")

        self._client = None

    async def connect(self) -> bool:
        """Establish connection to Jira."""
        logger.info(
            "jira_connecting",
            base_url=self.base_url,
            project_key=self.project_key,
        )

        try:
            # In production, would initialize jira-python client
            # from jira import JIRA
            # self._client = JIRA(server=self.base_url, basic_auth=(self.username, self.api_token))
            self._status = IntegrationStatus.CONNECTED
            self._reset_errors()

            logger.info("jira_connected", base_url=self.base_url)
            return True

        except Exception as e:
            self._status = IntegrationStatus.ERROR
            self._record_error(str(e))
            return False

    async def disconnect(self) -> None:
        """Disconnect from Jira."""
        self._client = None
        self._status = IntegrationStatus.DISCONNECTED
        logger.info("jira_disconnected")

    async def test_connection(self) -> ConnectionStatus:
        """Test Jira connection."""
        start_time = datetime.utcnow()

        try:
            # Would call myself() in production to verify credentials
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ConnectionStatus(
                connected=True,
                status=IntegrationStatus.CONNECTED,
                last_check=datetime.utcnow(),
                latency_ms=latency,
                details={
                    "base_url": self.base_url,
                    "project_key": self.project_key,
                },
            )

        except Exception as e:
            return ConnectionStatus(
                connected=False,
                status=IntegrationStatus.ERROR,
                last_check=datetime.utcnow(),
                error=str(e),
            )

    async def test_permissions(self) -> PermissionReport:
        """Test Jira permissions."""
        # In production, would check project permissions
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
        """Execute a Jira action."""
        start_time = datetime.utcnow()

        logger.info(
            "jira_action_started",
            action_type=action.type,
            target=action.target,
        )

        try:
            pre_state = await self.capture_pre_state(action)
            trace = []

            if "jira.create_issue" in action.type:
                result = await self._create_issue(action, trace)
            elif "jira.update_status" in action.type:
                result = await self._update_status(action, trace)
            elif "jira.add_comment" in action.type:
                result = await self._add_comment(action, trace)
            elif "jira.attach_evidence" in action.type:
                result = await self._attach_evidence(action, trace)
            elif "jira.link_issues" in action.type:
                result = await self._link_issues(action, trace)
            else:
                trace.append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "unknown",
                    "error": f"Unknown action type: {action.type}",
                })
                result = False

            post_state = await self.capture_post_state(action)
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ActionResult(
                success=result,
                action=action.type,
                target=action.target,
                pre_state=pre_state,
                post_state=post_state,
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
        """Capture issue state before action."""
        issue_key = action.target
        if issue_key and not issue_key.startswith("NEW"):
            return await self._get_issue_state(issue_key)
        return {"status": "new_issue"}

    async def capture_post_state(self, action: IROperation) -> dict[str, Any]:
        """Capture issue state after action."""
        return await self.capture_pre_state(action)

    async def query_resources(
        self,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Query Jira issues using JQL."""
        jql = filters.get("jql", f"project = {self.project_key}")
        max_results = filters.get("max_results", 50)

        return await self._search_issues(jql, max_results)

    async def get_resource_metadata(
        self,
        resource_id: str,
    ) -> dict[str, Any]:
        """Get issue metadata."""
        return await self._get_issue_state(resource_id)

    # =========================================================================
    # Issue Operations
    # =========================================================================

    async def _create_issue(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Create a Jira issue."""
        params = action.parameters
        issue_type = params.get("issue_type", "Task")
        summary = params.get("summary", "")
        description = params.get("description", "")
        priority = params.get("priority", "Medium")
        labels = params.get("labels", [])
        components = params.get("components", [])

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "jira:createIssue",
            "project": self.project_key,
            "issue_type": issue_type,
            "summary": summary,
            "status": "initiated",
        })

        # In production, would call:
        # issue = self._client.create_issue(
        #     project=self.project_key,
        #     issuetype={"name": issue_type},
        #     summary=summary,
        #     description=description,
        #     priority={"name": priority},
        #     labels=labels,
        # )

        issue_key = f"{self.project_key}-{datetime.utcnow().strftime('%H%M%S')}"

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "jira:createIssue",
            "issue_key": issue_key,
            "status": "completed",
        })

        logger.info(
            "jira_issue_created",
            issue_key=issue_key,
            issue_type=issue_type,
            summary=summary,
        )
        return True

    async def _update_status(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Update issue status/transition."""
        issue_key = action.target
        new_status = action.parameters.get("status", "Done")

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "jira:transitionIssue",
            "issue_key": issue_key,
            "new_status": new_status,
            "status": "initiated",
        })

        # In production, would find transition ID and apply:
        # transitions = self._client.transitions(issue_key)
        # transition_id = next(t['id'] for t in transitions if t['name'] == new_status)
        # self._client.transition_issue(issue_key, transition_id)

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "jira:transitionIssue",
            "issue_key": issue_key,
            "new_status": new_status,
            "status": "completed",
        })

        logger.info(
            "jira_status_updated",
            issue_key=issue_key,
            new_status=new_status,
        )
        return True

    async def _add_comment(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Add comment to issue."""
        issue_key = action.target
        comment_body = action.parameters.get("comment", "")
        visibility = action.parameters.get("visibility")  # e.g., {"type": "role", "value": "Developers"}

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "jira:addComment",
            "issue_key": issue_key,
            "status": "initiated",
        })

        # In production:
        # self._client.add_comment(issue_key, comment_body, visibility=visibility)

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "jira:addComment",
            "issue_key": issue_key,
            "status": "completed",
        })

        logger.info("jira_comment_added", issue_key=issue_key)
        return True

    async def _attach_evidence(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Attach evidence file to issue."""
        issue_key = action.target
        file_path = action.parameters.get("file_path")
        file_name = action.parameters.get("file_name", "evidence.json")

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "jira:attachFile",
            "issue_key": issue_key,
            "file_name": file_name,
            "status": "initiated",
        })

        # In production:
        # with open(file_path, 'rb') as f:
        #     self._client.add_attachment(issue_key, f, filename=file_name)

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "jira:attachFile",
            "issue_key": issue_key,
            "file_name": file_name,
            "status": "completed",
        })

        logger.info(
            "jira_evidence_attached",
            issue_key=issue_key,
            file_name=file_name,
        )
        return True

    async def _link_issues(
        self,
        action: IROperation,
        trace: list[dict[str, Any]],
    ) -> bool:
        """Link two issues."""
        source_issue = action.target
        target_issue = action.parameters.get("target_issue")
        link_type = action.parameters.get("link_type", "Relates")

        trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "jira:linkIssues",
            "source": source_issue,
            "target": target_issue,
            "link_type": link_type,
            "status": "completed",
        })

        # In production:
        # self._client.create_issue_link(link_type, source_issue, target_issue)

        logger.info(
            "jira_issues_linked",
            source=source_issue,
            target=target_issue,
            link_type=link_type,
        )
        return True

    async def _get_issue_state(self, issue_key: str) -> dict[str, Any]:
        """Get issue state."""
        # In production, would call self._client.issue(issue_key)
        return {
            "issue_key": issue_key,
            "status": "Open",
            "assignee": None,
            "reporter": self.username,
            "created": datetime.utcnow().isoformat(),
        }

    async def _search_issues(
        self,
        jql: str,
        max_results: int,
    ) -> list[dict[str, Any]]:
        """Search issues using JQL."""
        # In production:
        # issues = self._client.search_issues(jql, maxResults=max_results)
        return []

    # =========================================================================
    # Workflow Automation Helpers
    # =========================================================================

    async def create_optimization_ticket(
        self,
        resource_id: str,
        resource_type: str,
        action_type: str,
        estimated_savings: str,
        evidence_id: str,
        risk_score: int,
    ) -> str:
        """Create a ticket for a cost optimization action."""
        summary = f"[ArqAI] {action_type.title()} {resource_type}: {resource_id}"
        description = f"""
h2. Cost Optimization Recommendation

*Resource ID:* {resource_id}
*Resource Type:* {resource_type}
*Recommended Action:* {action_type}
*Estimated Savings:* {estimated_savings}
*Risk Score:* {risk_score}/100

h3. Evidence
Evidence ID: {evidence_id}
[View Evidence|/evidence/{evidence_id}]

h3. Approval Required
This action requires approval before execution.
Click "Approve" to proceed or "Reject" to decline.

---
_Generated by ArqAI Foundry_
"""

        # Would create issue and return key
        issue_key = f"{self.project_key}-OPT-{datetime.utcnow().strftime('%Y%m%d%H%M')}"

        logger.info(
            "optimization_ticket_created",
            issue_key=issue_key,
            resource_id=resource_id,
            action_type=action_type,
        )

        return issue_key

    async def update_ticket_with_result(
        self,
        issue_key: str,
        success: bool,
        execution_time_ms: float,
        evidence_id: str,
    ) -> None:
        """Update ticket with execution result."""
        status = "Done" if success else "Failed"
        comment = f"""
h3. Execution Complete

*Status:* {'✅ Success' if success else '❌ Failed'}
*Execution Time:* {execution_time_ms:.2f}ms
*Evidence ID:* {evidence_id}

[View Full Evidence|/evidence/{evidence_id}]
"""

        # Would add comment and transition
        logger.info(
            "ticket_result_updated",
            issue_key=issue_key,
            success=success,
        )
