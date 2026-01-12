"""Workspace management endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.studio.workspace import get_workspace_manager

router = APIRouter()


# =========================================================================
# Request Models
# =========================================================================

class CreateWorkspaceRequest(BaseModel):
    tenant_id: str
    name: str
    owner_id: str
    description: str = ""


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    settings: dict[str, Any] | None = None


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = "member"


class UpdateMemberRoleRequest(BaseModel):
    new_role: str


# =========================================================================
# Workspace CRUD
# =========================================================================

@router.post("")
async def create_workspace(request: CreateWorkspaceRequest) -> dict[str, Any]:
    """Create a new workspace."""
    manager = get_workspace_manager()

    workspace = manager.create_workspace(
        tenant_id=request.tenant_id,
        name=request.name,
        owner_id=request.owner_id,
        description=request.description,
    )

    return {
        "workspace_id": str(workspace.workspace_id),
        "name": workspace.name,
        "tenant_id": workspace.tenant_id,
        "owner_id": workspace.owner_id,
        "created_at": workspace.created_at.isoformat(),
    }


@router.get("")
async def list_workspaces(
    tenant_id: str = Query(..., description="Tenant ID"),
    user_id: str | None = Query(None, description="Filter by user membership"),
) -> dict[str, Any]:
    """List workspaces for a tenant."""
    manager = get_workspace_manager()
    workspaces = manager.list_workspaces(tenant_id, user_id)

    return {
        "workspaces": [
            {
                "workspace_id": str(w.workspace_id),
                "name": w.name,
                "description": w.description,
                "member_count": len(w.members),
                "agent_count": len(w.agents),
                "created_at": w.created_at.isoformat(),
            }
            for w in workspaces
        ],
        "total": len(workspaces),
    }


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: UUID) -> dict[str, Any]:
    """Get workspace details."""
    manager = get_workspace_manager()
    workspace = manager.get_workspace(workspace_id)

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return {
        "workspace_id": str(workspace.workspace_id),
        "tenant_id": workspace.tenant_id,
        "name": workspace.name,
        "description": workspace.description,
        "owner_id": workspace.owner_id,
        "members": workspace.members,
        "agent_count": len(workspace.agents),
        "settings": workspace.settings,
        "created_at": workspace.created_at.isoformat(),
        "updated_at": workspace.updated_at.isoformat(),
    }


@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: UUID,
    request: UpdateWorkspaceRequest,
) -> dict[str, Any]:
    """Update workspace settings."""
    manager = get_workspace_manager()

    updates = {}
    if request.name:
        updates["name"] = request.name
    if request.description:
        updates["description"] = request.description
    if request.settings:
        updates["settings"] = request.settings

    workspace = manager.update_workspace(workspace_id, updates)

    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return {
        "workspace_id": str(workspace.workspace_id),
        "name": workspace.name,
        "updated_at": workspace.updated_at.isoformat(),
    }


@router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: UUID) -> dict[str, Any]:
    """Delete a workspace."""
    manager = get_workspace_manager()

    try:
        deleted = manager.delete_workspace(workspace_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Workspace not found")
        return {"deleted": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# Team Management
# =========================================================================

@router.post("/{workspace_id}/members")
async def add_member(
    workspace_id: UUID,
    request: AddMemberRequest,
) -> dict[str, Any]:
    """Add a member to workspace."""
    manager = get_workspace_manager()

    added = manager.add_member(workspace_id, request.user_id, request.role)

    if not added:
        raise HTTPException(
            status_code=400,
            detail="Could not add member (workspace not found or user already member)",
        )

    return {"added": True, "user_id": request.user_id, "role": request.role}


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_member(
    workspace_id: UUID,
    user_id: str,
) -> dict[str, Any]:
    """Remove a member from workspace."""
    manager = get_workspace_manager()

    try:
        removed = manager.remove_member(workspace_id, user_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Member not found")
        return {"removed": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{workspace_id}/members/{user_id}")
async def update_member_role(
    workspace_id: UUID,
    user_id: str,
    request: UpdateMemberRoleRequest,
) -> dict[str, Any]:
    """Update a member's role."""
    manager = get_workspace_manager()

    updated = manager.update_member_role(workspace_id, user_id, request.new_role)

    if not updated:
        raise HTTPException(status_code=404, detail="Member not found")

    return {"updated": True, "new_role": request.new_role}


# =========================================================================
# Workspace Agents
# =========================================================================

@router.get("/{workspace_id}/agents")
async def list_workspace_agents(
    workspace_id: UUID,
    status: str | None = Query(None, description="Filter by status"),
) -> dict[str, Any]:
    """List agents in workspace."""
    manager = get_workspace_manager()
    agents = manager.list_agents(workspace_id, status_filter=status)

    return {
        "agents": [
            {
                "agent_id": str(a.agent_id),
                "name": a.name,
                "template_id": a.template_id,
                "status": a.status,
                "last_activity": a.last_activity.isoformat(),
                "metrics": a.metrics,
            }
            for a in agents
        ],
        "total": len(agents),
    }


@router.patch("/{workspace_id}/agents/{agent_id}/status")
async def update_agent_status(
    workspace_id: UUID,
    agent_id: UUID,
    status: str = Query(..., description="New status"),
) -> dict[str, Any]:
    """Update agent status."""
    manager = get_workspace_manager()

    updated = manager.update_agent_status(workspace_id, agent_id, status)

    if not updated:
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"updated": True, "status": status}


# =========================================================================
# Dashboard
# =========================================================================

@router.get("/{workspace_id}/summary")
async def get_workspace_summary(workspace_id: UUID) -> dict[str, Any]:
    """Get workspace summary for dashboard."""
    manager = get_workspace_manager()
    summary = manager.get_workspace_summary(workspace_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Workspace not found")

    return summary


@router.get("/tenant/{tenant_id}/summary")
async def get_tenant_summary(tenant_id: str) -> dict[str, Any]:
    """Get tenant-wide summary."""
    manager = get_workspace_manager()
    return manager.get_tenant_summary(tenant_id)
