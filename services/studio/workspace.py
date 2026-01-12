"""
Workspace Management

Manages user workspaces for agent building and management.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from services.templates.base import InstantiatedAgent

logger = structlog.get_logger(__name__)


@dataclass
class WorkspaceAgent:
    """An agent in a workspace."""
    agent_id: UUID
    name: str
    template_id: str
    status: str  # active, paused, stopped, error
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class Workspace:
    """A user's workspace containing agents and configurations."""
    workspace_id: UUID = field(default_factory=uuid4)
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    owner_id: str = ""
    members: list[dict[str, str]] = field(default_factory=list)
    agents: dict[UUID, WorkspaceAgent] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class WorkspaceManager:
    """
    Manages workspaces for agent building and management.

    Features:
    - Multi-tenant workspace isolation
    - Team collaboration
    - Agent lifecycle management
    - Usage tracking
    """

    def __init__(self):
        self._workspaces: dict[UUID, Workspace] = {}
        self._tenant_workspaces: dict[str, list[UUID]] = {}

    # =========================================================================
    # Workspace CRUD
    # =========================================================================

    def create_workspace(
        self,
        tenant_id: str,
        name: str,
        owner_id: str,
        description: str = "",
    ) -> Workspace:
        """Create a new workspace."""
        workspace = Workspace(
            tenant_id=tenant_id,
            name=name,
            description=description,
            owner_id=owner_id,
            members=[{"user_id": owner_id, "role": "owner"}],
        )

        self._workspaces[workspace.workspace_id] = workspace

        if tenant_id not in self._tenant_workspaces:
            self._tenant_workspaces[tenant_id] = []
        self._tenant_workspaces[tenant_id].append(workspace.workspace_id)

        logger.info(
            "workspace_created",
            workspace_id=str(workspace.workspace_id),
            tenant_id=tenant_id,
            owner_id=owner_id,
        )

        return workspace

    def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        """Get a workspace by ID."""
        return self._workspaces.get(workspace_id)

    def list_workspaces(
        self,
        tenant_id: str,
        user_id: str | None = None,
    ) -> list[Workspace]:
        """List workspaces for a tenant, optionally filtered by user."""
        workspace_ids = self._tenant_workspaces.get(tenant_id, [])
        workspaces = [
            self._workspaces[wid] for wid in workspace_ids
            if wid in self._workspaces
        ]

        if user_id:
            workspaces = [
                w for w in workspaces
                if any(m["user_id"] == user_id for m in w.members)
            ]

        return workspaces

    def update_workspace(
        self,
        workspace_id: UUID,
        updates: dict[str, Any],
    ) -> Workspace | None:
        """Update workspace settings."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return None

        if "name" in updates:
            workspace.name = updates["name"]
        if "description" in updates:
            workspace.description = updates["description"]
        if "settings" in updates:
            workspace.settings.update(updates["settings"])

        workspace.updated_at = datetime.utcnow()

        logger.info(
            "workspace_updated",
            workspace_id=str(workspace_id),
            updates=list(updates.keys()),
        )

        return workspace

    def delete_workspace(self, workspace_id: UUID) -> bool:
        """Delete a workspace."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False

        # Check for active agents
        if any(a.status == "active" for a in workspace.agents.values()):
            raise ValueError("Cannot delete workspace with active agents")

        # Remove from tenant list
        if workspace.tenant_id in self._tenant_workspaces:
            self._tenant_workspaces[workspace.tenant_id].remove(workspace_id)

        del self._workspaces[workspace_id]

        logger.info("workspace_deleted", workspace_id=str(workspace_id))
        return True

    # =========================================================================
    # Team Management
    # =========================================================================

    def add_member(
        self,
        workspace_id: UUID,
        user_id: str,
        role: str = "member",
    ) -> bool:
        """Add a member to workspace."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False

        # Check if already member
        if any(m["user_id"] == user_id for m in workspace.members):
            return False

        workspace.members.append({
            "user_id": user_id,
            "role": role,
            "added_at": datetime.utcnow().isoformat(),
        })
        workspace.updated_at = datetime.utcnow()

        logger.info(
            "workspace_member_added",
            workspace_id=str(workspace_id),
            user_id=user_id,
            role=role,
        )

        return True

    def remove_member(
        self,
        workspace_id: UUID,
        user_id: str,
    ) -> bool:
        """Remove a member from workspace."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False

        # Cannot remove owner
        if any(m["user_id"] == user_id and m["role"] == "owner" for m in workspace.members):
            raise ValueError("Cannot remove workspace owner")

        original_count = len(workspace.members)
        workspace.members = [
            m for m in workspace.members if m["user_id"] != user_id
        ]

        if len(workspace.members) < original_count:
            workspace.updated_at = datetime.utcnow()
            logger.info(
                "workspace_member_removed",
                workspace_id=str(workspace_id),
                user_id=user_id,
            )
            return True

        return False

    def update_member_role(
        self,
        workspace_id: UUID,
        user_id: str,
        new_role: str,
    ) -> bool:
        """Update a member's role."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False

        for member in workspace.members:
            if member["user_id"] == user_id:
                member["role"] = new_role
                workspace.updated_at = datetime.utcnow()
                return True

        return False

    # =========================================================================
    # Agent Management
    # =========================================================================

    def add_agent(
        self,
        workspace_id: UUID,
        agent: InstantiatedAgent,
    ) -> WorkspaceAgent | None:
        """Add an agent to workspace."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return None

        workspace_agent = WorkspaceAgent(
            agent_id=agent.agent_id,
            name=agent.name,
            template_id=agent.template_id,
            status="active",
        )

        workspace.agents[agent.agent_id] = workspace_agent
        workspace.updated_at = datetime.utcnow()

        logger.info(
            "agent_added_to_workspace",
            workspace_id=str(workspace_id),
            agent_id=str(agent.agent_id),
        )

        return workspace_agent

    def remove_agent(
        self,
        workspace_id: UUID,
        agent_id: UUID,
    ) -> bool:
        """Remove an agent from workspace."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False

        if agent_id not in workspace.agents:
            return False

        del workspace.agents[agent_id]
        workspace.updated_at = datetime.utcnow()

        logger.info(
            "agent_removed_from_workspace",
            workspace_id=str(workspace_id),
            agent_id=str(agent_id),
        )

        return True

    def update_agent_status(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        status: str,
    ) -> bool:
        """Update agent status."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False

        if agent_id not in workspace.agents:
            return False

        workspace.agents[agent_id].status = status
        workspace.agents[agent_id].last_activity = datetime.utcnow()
        workspace.updated_at = datetime.utcnow()

        logger.info(
            "agent_status_updated",
            workspace_id=str(workspace_id),
            agent_id=str(agent_id),
            status=status,
        )

        return True

    def list_agents(
        self,
        workspace_id: UUID,
        status_filter: str | None = None,
    ) -> list[WorkspaceAgent]:
        """List agents in workspace."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return []

        agents = list(workspace.agents.values())

        if status_filter:
            agents = [a for a in agents if a.status == status_filter]

        return agents

    def update_agent_metrics(
        self,
        workspace_id: UUID,
        agent_id: UUID,
        metrics: dict[str, Any],
    ) -> bool:
        """Update agent metrics."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return False

        if agent_id not in workspace.agents:
            return False

        workspace.agents[agent_id].metrics.update(metrics)
        workspace.agents[agent_id].last_activity = datetime.utcnow()

        return True

    # =========================================================================
    # Dashboard Data
    # =========================================================================

    def get_workspace_summary(
        self,
        workspace_id: UUID,
    ) -> dict[str, Any]:
        """Get workspace summary for dashboard."""
        workspace = self._workspaces.get(workspace_id)
        if not workspace:
            return {}

        agents = list(workspace.agents.values())

        return {
            "workspace_id": str(workspace.workspace_id),
            "name": workspace.name,
            "tenant_id": workspace.tenant_id,
            "member_count": len(workspace.members),
            "agent_stats": {
                "total": len(agents),
                "active": len([a for a in agents if a.status == "active"]),
                "paused": len([a for a in agents if a.status == "paused"]),
                "stopped": len([a for a in agents if a.status == "stopped"]),
                "error": len([a for a in agents if a.status == "error"]),
            },
            "recent_activity": self._get_recent_activity(workspace),
            "created_at": workspace.created_at.isoformat(),
            "updated_at": workspace.updated_at.isoformat(),
        }

    def get_tenant_summary(
        self,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Get tenant-wide summary."""
        workspaces = self.list_workspaces(tenant_id)

        total_agents = 0
        active_agents = 0
        all_members = set()

        for ws in workspaces:
            total_agents += len(ws.agents)
            active_agents += len([a for a in ws.agents.values() if a.status == "active"])
            all_members.update(m["user_id"] for m in ws.members)

        return {
            "tenant_id": tenant_id,
            "workspace_count": len(workspaces),
            "total_agents": total_agents,
            "active_agents": active_agents,
            "unique_users": len(all_members),
        }

    def _get_recent_activity(
        self,
        workspace: Workspace,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get recent activity for workspace."""
        # Would pull from activity log
        return []


# =========================================================================
# Global Instance
# =========================================================================

_workspace_manager: WorkspaceManager | None = None


def get_workspace_manager() -> WorkspaceManager:
    """Get global workspace manager."""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager()
    return _workspace_manager
