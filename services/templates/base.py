"""
Template Base Classes

Defines the structure for agent templates.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import structlog

from arqai_foundry.core.enums import DataClassification, RiskTier

logger = structlog.get_logger(__name__)


class TemplateCategory(str, Enum):
    """Categories of templates."""
    COST_OPTIMIZATION = "cost_optimization"
    COMPLIANCE = "compliance"
    SECURITY = "security"
    OPERATIONS = "operations"
    DATA_MANAGEMENT = "data_management"
    WORKFLOW = "workflow"
    ANALYTICS = "analytics"
    CUSTOM = "custom"


class TemplateVertical(str, Enum):
    """Industry verticals."""
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    ENERGY = "energy"
    GOVERNMENT = "government"
    GENERAL = "general"


class CustomizationLevel(str, Enum):
    """Level of customization allowed."""
    NONE = "none"  # Template is fixed
    PARAMETERS_ONLY = "parameters_only"  # Can only change parameters
    PARTIAL = "partial"  # Can modify some components
    FULL = "full"  # Full customization allowed


@dataclass
class TemplateVersion:
    """Version information for a template."""
    major: int = 1
    minor: int = 0
    patch: int = 0
    release_date: datetime = field(default_factory=datetime.utcnow)
    changelog: str = ""

    @property
    def version_string(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def is_compatible_with(self, other: "TemplateVersion") -> bool:
        """Check if compatible (same major version)."""
        return self.major == other.major


@dataclass
class TemplateParameter:
    """A customizable parameter in a template."""
    name: str
    description: str
    param_type: str  # string, number, boolean, list, object
    default_value: Any
    required: bool = False
    validation_rules: dict[str, Any] = field(default_factory=dict)
    allowed_values: list[Any] | None = None
    sensitive: bool = False  # If true, value is encrypted

    def validate(self, value: Any) -> tuple[bool, str | None]:
        """Validate a parameter value."""
        # Type check
        type_map = {
            "string": str,
            "number": (int, float),
            "boolean": bool,
            "list": list,
            "object": dict,
        }

        expected_type = type_map.get(self.param_type)
        if expected_type and not isinstance(value, expected_type):
            return False, f"Expected {self.param_type}, got {type(value).__name__}"

        # Allowed values check
        if self.allowed_values and value not in self.allowed_values:
            return False, f"Value must be one of: {self.allowed_values}"

        # Custom validation rules
        if "min" in self.validation_rules:
            if value < self.validation_rules["min"]:
                return False, f"Value must be >= {self.validation_rules['min']}"

        if "max" in self.validation_rules:
            if value > self.validation_rules["max"]:
                return False, f"Value must be <= {self.validation_rules['max']}"

        if "pattern" in self.validation_rules:
            import re
            if not re.match(self.validation_rules["pattern"], str(value)):
                return False, f"Value must match pattern: {self.validation_rules['pattern']}"

        return True, None


@dataclass
class TemplateCapability:
    """A capability provided by the template."""
    name: str
    description: str
    action_types: list[str]
    required_permissions: list[str]
    risk_tier: RiskTier = RiskTier.LOW
    data_classification: DataClassification = DataClassification.INTERNAL
    enabled_by_default: bool = True
    customizable: bool = True


@dataclass
class TemplatePolicy:
    """Policy configuration for a template."""
    policy_id: str
    name: str
    description: str
    default_enabled: bool = True
    customizable: bool = False
    policy_definition: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemplateIntegration:
    """Integration required by a template."""
    integration_type: str  # aws, jira, slack, teams, etc.
    required: bool = True
    configuration_schema: dict[str, Any] = field(default_factory=dict)
    default_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemplateConfig:
    """Configuration for instantiating a template."""
    template_id: str
    tenant_id: str
    name: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    enabled_capabilities: list[str] = field(default_factory=list)
    disabled_capabilities: list[str] = field(default_factory=list)
    policy_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    integration_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    custom_actions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTemplate:
    """
    Base class for agent templates.

    Templates are 70% pre-built with common functionality,
    allowing enterprises to customize the remaining 30%.
    """

    template_id: str
    name: str
    description: str
    category: TemplateCategory
    vertical: TemplateVertical
    version: TemplateVersion

    # Pre-built components (70%)
    capabilities: list[TemplateCapability] = field(default_factory=list)
    default_policies: list[TemplatePolicy] = field(default_factory=list)
    default_workflows: list[dict[str, Any]] = field(default_factory=list)
    integrations: list[TemplateIntegration] = field(default_factory=list)

    # Customizable components (30%)
    parameters: list[TemplateParameter] = field(default_factory=list)
    customization_level: CustomizationLevel = CustomizationLevel.PARTIAL

    # Metadata
    author: str = "ArqAI"
    license: str = "Enterprise"
    tags: list[str] = field(default_factory=list)
    documentation_url: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def validate_config(
        self,
        config: TemplateConfig,
    ) -> tuple[bool, list[str]]:
        """Validate a template configuration."""
        errors = []

        # Validate parameters
        for param in self.parameters:
            value = config.parameters.get(param.name, param.default_value)

            if param.required and value is None:
                errors.append(f"Required parameter '{param.name}' is missing")
                continue

            if value is not None:
                valid, error = param.validate(value)
                if not valid:
                    errors.append(f"Parameter '{param.name}': {error}")

        # Validate capabilities
        for cap_name in config.enabled_capabilities:
            if not any(c.name == cap_name for c in self.capabilities):
                errors.append(f"Unknown capability: {cap_name}")

        # Check required integrations
        for integration in self.integrations:
            if integration.required:
                if integration.integration_type not in config.integration_configs:
                    errors.append(
                        f"Required integration '{integration.integration_type}' not configured"
                    )

        return len(errors) == 0, errors

    def get_effective_capabilities(
        self,
        config: TemplateConfig,
    ) -> list[TemplateCapability]:
        """Get the effective capabilities based on config."""
        effective = []

        for cap in self.capabilities:
            # Check if explicitly disabled
            if cap.name in config.disabled_capabilities:
                continue

            # Check if explicitly enabled or enabled by default
            if cap.name in config.enabled_capabilities or cap.enabled_by_default:
                effective.append(cap)

        return effective

    def get_parameter_value(
        self,
        param_name: str,
        config: TemplateConfig,
    ) -> Any:
        """Get parameter value from config or default."""
        if param_name in config.parameters:
            return config.parameters[param_name]

        for param in self.parameters:
            if param.name == param_name:
                return param.default_value

        return None

    def get_effective_policies(
        self,
        config: TemplateConfig,
    ) -> list[dict[str, Any]]:
        """Get effective policies with overrides applied."""
        policies = []

        for policy in self.default_policies:
            effective_policy = policy.policy_definition.copy()

            # Apply overrides if allowed
            if policy.customizable and policy.policy_id in config.policy_overrides:
                override = config.policy_overrides[policy.policy_id]
                effective_policy.update(override)

            policies.append({
                "policy_id": policy.policy_id,
                "name": policy.name,
                "enabled": policy.default_enabled,
                "definition": effective_policy,
            })

        return policies

    def to_dict(self) -> dict[str, Any]:
        """Convert template to dictionary."""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "vertical": self.vertical.value,
            "version": self.version.version_string,
            "capabilities": [
                {
                    "name": c.name,
                    "description": c.description,
                    "risk_tier": c.risk_tier.value,
                    "enabled_by_default": c.enabled_by_default,
                }
                for c in self.capabilities
            ],
            "parameters": [
                {
                    "name": p.name,
                    "description": p.description,
                    "type": p.param_type,
                    "default": p.default_value,
                    "required": p.required,
                }
                for p in self.parameters
            ],
            "integrations": [
                {
                    "type": i.integration_type,
                    "required": i.required,
                }
                for i in self.integrations
            ],
            "customization_level": self.customization_level.value,
            "tags": self.tags,
            "author": self.author,
        }


@dataclass
class InstantiatedAgent:
    """An agent instantiated from a template."""
    agent_id: UUID = field(default_factory=uuid4)
    template_id: str = ""
    tenant_id: str = ""
    name: str = ""
    config: TemplateConfig | None = None
    effective_capabilities: list[TemplateCapability] = field(default_factory=list)
    effective_policies: list[dict[str, Any]] = field(default_factory=list)
    status: str = "created"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
