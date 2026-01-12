"""Agent Builder Studio endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.studio.builder import AgentBuilder
from services.templates.engine import TemplateEngine
from services.templates.registry import get_template_registry

router = APIRouter()

# Dependencies - would be injected in production
_builder: AgentBuilder | None = None


def get_builder() -> AgentBuilder:
    """Get agent builder instance."""
    global _builder
    if _builder is None:
        registry = get_template_registry()
        engine = TemplateEngine()
        _builder = AgentBuilder(registry, engine)
    return _builder


# =========================================================================
# Request Models
# =========================================================================

class CreateSessionRequest(BaseModel):
    tenant_id: str
    user_id: str


class SelectTemplateRequest(BaseModel):
    template_id: str


class UpdateParameterRequest(BaseModel):
    parameter_name: str
    value: Any


class UpdateCapabilitiesRequest(BaseModel):
    enabled: list[str] | None = None
    disabled: list[str] | None = None


class PolicyOverrideRequest(BaseModel):
    policy_id: str
    overrides: dict[str, Any]


class IntegrationConfigRequest(BaseModel):
    integration_type: str
    config: dict[str, Any]


class DeployAgentRequest(BaseModel):
    agent_name: str


# =========================================================================
# Session Endpoints
# =========================================================================

@router.post("/sessions")
async def create_session(request: CreateSessionRequest) -> dict[str, Any]:
    """Create a new agent building session."""
    builder = get_builder()
    session = builder.create_session(request.tenant_id, request.user_id)

    return {
        "session_id": str(session.session_id),
        "status": session.status,
        "created_at": session.created_at.isoformat(),
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID) -> dict[str, Any]:
    """Get session details."""
    builder = get_builder()
    session = builder.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": str(session.session_id),
        "tenant_id": session.tenant_id,
        "user_id": session.user_id,
        "template_id": session.template_id,
        "draft_config": session.draft_config,
        "status": session.status,
        "validation_results": session.validation_results,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: UUID) -> dict[str, Any]:
    """Delete a building session."""
    builder = get_builder()
    deleted = builder.delete_session(session_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": True}


# =========================================================================
# Template Selection
# =========================================================================

@router.post("/sessions/{session_id}/template")
async def select_template(
    session_id: UUID,
    request: SelectTemplateRequest,
) -> dict[str, Any]:
    """Select a template for the building session."""
    builder = get_builder()

    try:
        result = builder.select_template(session_id, request.template_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# Configuration (30% Customization)
# =========================================================================

@router.put("/sessions/{session_id}/parameters")
async def update_parameter(
    session_id: UUID,
    request: UpdateParameterRequest,
) -> dict[str, Any]:
    """Update a customizable parameter."""
    builder = get_builder()

    try:
        result = builder.update_parameter(
            session_id,
            request.parameter_name,
            request.value,
        )
        return {
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/sessions/{session_id}/capabilities")
async def update_capabilities(
    session_id: UUID,
    request: UpdateCapabilitiesRequest,
) -> dict[str, Any]:
    """Update enabled/disabled capabilities."""
    builder = get_builder()

    try:
        result = builder.update_capabilities(
            session_id,
            enabled=request.enabled,
            disabled=request.disabled,
        )
        return {
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/sessions/{session_id}/policies")
async def update_policy_override(
    session_id: UUID,
    request: PolicyOverrideRequest,
) -> dict[str, Any]:
    """Update policy overrides."""
    builder = get_builder()

    try:
        result = builder.update_policy_override(
            session_id,
            request.policy_id,
            request.overrides,
        )
        return {
            "valid": result.valid,
            "errors": result.errors,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/sessions/{session_id}/integrations")
async def configure_integration(
    session_id: UUID,
    request: IntegrationConfigRequest,
) -> dict[str, Any]:
    """Configure an integration."""
    builder = get_builder()

    try:
        result = builder.configure_integration(
            session_id,
            request.integration_type,
            request.config,
        )
        return {
            "valid": result.valid,
            "errors": result.errors,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# Validation & Testing
# =========================================================================

@router.post("/sessions/{session_id}/validate")
async def validate_configuration(session_id: UUID) -> dict[str, Any]:
    """Validate the agent configuration."""
    builder = get_builder()

    try:
        result = builder.validate_configuration(session_id)
        return {
            "valid": result.valid,
            "errors": result.errors,
            "warnings": result.warnings,
            "suggestions": result.suggestions,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/test")
async def test_configuration(session_id: UUID) -> dict[str, Any]:
    """Test the agent configuration in a sandbox."""
    builder = get_builder()

    try:
        result = await builder.test_configuration(session_id)
        return {
            "success": result.success,
            "test_cases": result.test_cases,
            "coverage": result.coverage,
            "performance_metrics": result.performance_metrics,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================================================================
# Deployment
# =========================================================================

@router.post("/sessions/{session_id}/deploy")
async def deploy_agent(
    session_id: UUID,
    request: DeployAgentRequest,
) -> dict[str, Any]:
    """Deploy the configured agent."""
    builder = get_builder()

    try:
        agent = await builder.deploy_agent(session_id, request.agent_name)
        return {
            "agent_id": str(agent.agent_id),
            "name": agent.name,
            "template_id": agent.template_id,
            "status": agent.status,
            "created_at": agent.created_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
