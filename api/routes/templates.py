"""Template management endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from services.templates.registry import get_template_registry

router = APIRouter()


@router.get("")
async def list_templates(
    category: str | None = Query(None, description="Filter by category"),
    vertical: str | None = Query(None, description="Filter by vertical"),
    tags: list[str] | None = Query(None, description="Filter by tags"),
) -> dict[str, Any]:
    """List available agent templates."""
    from services.templates.base import TemplateCategory, TemplateVertical

    registry = get_template_registry()

    cat = TemplateCategory(category) if category else None
    vert = TemplateVertical(vertical) if vertical else None

    templates = registry.list_templates(category=cat, vertical=vert, tags=tags)

    return {
        "templates": [t.to_dict() for t in templates],
        "total": len(templates),
    }


@router.get("/search")
async def search_templates(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
) -> dict[str, Any]:
    """Search templates by keyword."""
    registry = get_template_registry()
    templates = registry.search(query, limit)

    return {
        "templates": [t.to_dict() for t in templates],
        "total": len(templates),
        "query": query,
    }


@router.get("/categories")
async def list_categories() -> dict[str, Any]:
    """List all template categories."""
    registry = get_template_registry()
    categories = registry.get_categories()

    return {
        "categories": [c.value for c in categories],
    }


@router.get("/verticals")
async def list_verticals() -> dict[str, Any]:
    """List all industry verticals."""
    registry = get_template_registry()
    verticals = registry.get_verticals()

    return {
        "verticals": [v.value for v in verticals],
    }


@router.get("/tags")
async def list_tags() -> dict[str, Any]:
    """List all template tags."""
    registry = get_template_registry()

    return {
        "tags": registry.get_all_tags(),
    }


@router.get("/{template_id}")
async def get_template(template_id: str) -> dict[str, Any]:
    """Get template details."""
    registry = get_template_registry()
    template = registry.get(template_id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "template": template.to_dict(),
        "capabilities": [
            {
                "name": c.name,
                "description": c.description,
                "risk_tier": c.risk_tier.value,
                "enabled_by_default": c.enabled_by_default,
                "customizable": c.customizable,
            }
            for c in template.capabilities
        ],
        "parameters": [
            {
                "name": p.name,
                "description": p.description,
                "type": p.param_type,
                "default": p.default_value,
                "required": p.required,
                "allowed_values": p.allowed_values,
            }
            for p in template.parameters
        ],
        "policies": [
            {
                "policy_id": p.policy_id,
                "name": p.name,
                "description": p.description,
                "customizable": p.customizable,
            }
            for p in template.default_policies
        ],
        "integrations": [
            {
                "type": i.integration_type,
                "required": i.required,
            }
            for i in template.integrations
        ],
    }


@router.get("/{template_id}/versions")
async def get_template_versions(template_id: str) -> dict[str, Any]:
    """Get version history for a template."""
    registry = get_template_registry()
    versions = registry.get_version_history(template_id)

    if not versions:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "template_id": template_id,
        "versions": [
            {
                "version": v.version_string,
                "release_date": v.release_date.isoformat(),
                "changelog": v.changelog,
            }
            for v in versions
        ],
    }
