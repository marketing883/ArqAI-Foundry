"""
Template Registry

Central registry for managing agent templates.
"""

from datetime import datetime
from typing import Any

import structlog

from services.templates.base import (
    AgentTemplate,
    TemplateCategory,
    TemplateVertical,
    TemplateVersion,
)

logger = structlog.get_logger(__name__)


class TemplateRegistry:
    """
    Central registry for agent templates.

    Features:
    - Register and discover templates
    - Filter by category, vertical, tags
    - Version management
    - Template validation
    """

    def __init__(self):
        self._templates: dict[str, AgentTemplate] = {}
        self._version_history: dict[str, list[TemplateVersion]] = {}

    def register(
        self,
        template: AgentTemplate,
        overwrite: bool = False,
    ) -> bool:
        """
        Register a template.

        Args:
            template: Template to register
            overwrite: Whether to overwrite existing template

        Returns:
            True if registration successful
        """
        if template.template_id in self._templates and not overwrite:
            logger.warning(
                "template_already_exists",
                template_id=template.template_id,
            )
            return False

        # Validate template
        from services.templates.engine import TemplateValidator
        valid, errors = TemplateValidator.validate_template(template)

        if not valid:
            logger.error(
                "template_validation_failed",
                template_id=template.template_id,
                errors=errors,
            )
            return False

        self._templates[template.template_id] = template

        # Track version history
        if template.template_id not in self._version_history:
            self._version_history[template.template_id] = []
        self._version_history[template.template_id].append(template.version)

        logger.info(
            "template_registered",
            template_id=template.template_id,
            name=template.name,
            version=template.version.version_string,
        )

        return True

    def unregister(self, template_id: str) -> bool:
        """Unregister a template."""
        if template_id not in self._templates:
            return False

        del self._templates[template_id]
        logger.info("template_unregistered", template_id=template_id)
        return True

    def get(self, template_id: str) -> AgentTemplate | None:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def list_templates(
        self,
        category: TemplateCategory | None = None,
        vertical: TemplateVertical | None = None,
        tags: list[str] | None = None,
    ) -> list[AgentTemplate]:
        """
        List templates with optional filtering.

        Args:
            category: Filter by category
            vertical: Filter by vertical
            tags: Filter by tags (any match)

        Returns:
            List of matching templates
        """
        templates = list(self._templates.values())

        if category:
            templates = [t for t in templates if t.category == category]

        if vertical:
            templates = [t for t in templates if t.vertical == vertical]

        if tags:
            templates = [
                t for t in templates
                if any(tag in t.tags for tag in tags)
            ]

        return templates

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[AgentTemplate]:
        """
        Search templates by name or description.

        Args:
            query: Search query
            limit: Max results

        Returns:
            Matching templates
        """
        query_lower = query.lower()
        results = []

        for template in self._templates.values():
            # Check name
            if query_lower in template.name.lower():
                results.append((template, 2))  # Higher score for name match
                continue

            # Check description
            if query_lower in template.description.lower():
                results.append((template, 1))
                continue

            # Check tags
            if any(query_lower in tag.lower() for tag in template.tags):
                results.append((template, 1))

        # Sort by score and return
        results.sort(key=lambda x: x[1], reverse=True)
        return [t for t, _ in results[:limit]]

    def get_by_vertical(
        self,
        vertical: TemplateVertical,
    ) -> list[AgentTemplate]:
        """Get all templates for a specific vertical."""
        return [
            t for t in self._templates.values()
            if t.vertical == vertical
        ]

    def get_version_history(
        self,
        template_id: str,
    ) -> list[TemplateVersion]:
        """Get version history for a template."""
        return self._version_history.get(template_id, [])

    def get_latest_version(
        self,
        template_id: str,
    ) -> TemplateVersion | None:
        """Get the latest version of a template."""
        template = self._templates.get(template_id)
        return template.version if template else None

    def get_categories(self) -> list[TemplateCategory]:
        """Get all categories with registered templates."""
        return list(set(t.category for t in self._templates.values()))

    def get_verticals(self) -> list[TemplateVertical]:
        """Get all verticals with registered templates."""
        return list(set(t.vertical for t in self._templates.values()))

    def get_all_tags(self) -> list[str]:
        """Get all unique tags across templates."""
        tags = set()
        for template in self._templates.values():
            tags.update(template.tags)
        return sorted(tags)

    def export_catalog(self) -> dict[str, Any]:
        """Export template catalog as JSON-serializable dict."""
        return {
            "templates": [t.to_dict() for t in self._templates.values()],
            "categories": [c.value for c in self.get_categories()],
            "verticals": [v.value for v in self.get_verticals()],
            "tags": self.get_all_tags(),
            "exported_at": datetime.utcnow().isoformat(),
        }

    def import_templates(
        self,
        templates_data: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """
        Import templates from data.

        Args:
            templates_data: List of template dictionaries

        Returns:
            Tuple of (successful, failed) counts
        """
        successful = 0
        failed = 0

        for data in templates_data:
            try:
                template = self._dict_to_template(data)
                if self.register(template):
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(
                    "template_import_failed",
                    template_id=data.get("template_id"),
                    error=str(e),
                )
                failed += 1

        logger.info(
            "templates_imported",
            successful=successful,
            failed=failed,
        )

        return successful, failed

    def _dict_to_template(
        self,
        data: dict[str, Any],
    ) -> AgentTemplate:
        """Convert dictionary to AgentTemplate."""
        from services.templates.base import (
            CustomizationLevel,
            TemplateCapability,
            TemplateIntegration,
            TemplateParameter,
            TemplatePolicy,
        )
        from arqai_foundry.core.enums import DataClassification, RiskTier

        # Parse version
        version_parts = data.get("version", "1.0.0").split(".")
        version = TemplateVersion(
            major=int(version_parts[0]) if len(version_parts) > 0 else 1,
            minor=int(version_parts[1]) if len(version_parts) > 1 else 0,
            patch=int(version_parts[2]) if len(version_parts) > 2 else 0,
        )

        # Parse capabilities
        capabilities = []
        for cap_data in data.get("capabilities", []):
            capabilities.append(TemplateCapability(
                name=cap_data["name"],
                description=cap_data.get("description", ""),
                action_types=cap_data.get("action_types", []),
                required_permissions=cap_data.get("required_permissions", []),
                risk_tier=RiskTier(cap_data.get("risk_tier", "low")),
                data_classification=DataClassification(
                    cap_data.get("data_classification", "internal")
                ),
                enabled_by_default=cap_data.get("enabled_by_default", True),
            ))

        # Parse parameters
        parameters = []
        for param_data in data.get("parameters", []):
            parameters.append(TemplateParameter(
                name=param_data["name"],
                description=param_data.get("description", ""),
                param_type=param_data.get("type", "string"),
                default_value=param_data.get("default"),
                required=param_data.get("required", False),
                validation_rules=param_data.get("validation_rules", {}),
            ))

        # Parse integrations
        integrations = []
        for int_data in data.get("integrations", []):
            integrations.append(TemplateIntegration(
                integration_type=int_data["type"],
                required=int_data.get("required", True),
                configuration_schema=int_data.get("schema", {}),
            ))

        return AgentTemplate(
            template_id=data["template_id"],
            name=data["name"],
            description=data.get("description", ""),
            category=TemplateCategory(data.get("category", "custom")),
            vertical=TemplateVertical(data.get("vertical", "general")),
            version=version,
            capabilities=capabilities,
            parameters=parameters,
            integrations=integrations,
            customization_level=CustomizationLevel(
                data.get("customization_level", "partial")
            ),
            tags=data.get("tags", []),
            author=data.get("author", "ArqAI"),
        )


# =========================================================================
# Global Registry Instance
# =========================================================================

_global_registry: TemplateRegistry | None = None


def get_template_registry() -> TemplateRegistry:
    """Get the global template registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = TemplateRegistry()
    return _global_registry


def register_builtin_templates(registry: TemplateRegistry) -> None:
    """Register built-in templates with the registry."""
    # This will be populated by the vertical templates in BUILD 9
    logger.info("builtin_templates_registration_placeholder")
