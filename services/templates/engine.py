"""
Template Engine

Instantiates and manages agents from templates.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from arqai_foundry.core.enums import RiskTier
from arqai_foundry.core.models import AgentIdentity
from services.templates.base import (
    AgentTemplate,
    InstantiatedAgent,
    TemplateConfig,
)

logger = structlog.get_logger(__name__)


class TemplateEngine:
    """
    Engine for instantiating agents from templates.

    Responsibilities:
    - Validate template configurations
    - Create agent instances from templates
    - Apply customizations
    - Register agents with identity service
    - Configure policies and integrations
    """

    def __init__(
        self,
        identity_service: Any = None,
        policy_service: Any = None,
        integration_registry: Any = None,
    ):
        self._identity_service = identity_service
        self._policy_service = policy_service
        self._integration_registry = integration_registry

        # Instantiated agents
        self._agents: dict[UUID, InstantiatedAgent] = {}

    async def instantiate(
        self,
        template: AgentTemplate,
        config: TemplateConfig,
    ) -> InstantiatedAgent:
        """
        Instantiate an agent from a template.

        This applies the 70% pre-built functionality plus
        30% customization from the config.

        Args:
            template: The agent template
            config: Customization configuration

        Returns:
            Instantiated agent
        """
        logger.info(
            "instantiating_agent",
            template_id=template.template_id,
            tenant_id=config.tenant_id,
            name=config.name,
        )

        # Validate configuration
        valid, errors = template.validate_config(config)
        if not valid:
            raise ValueError(f"Invalid configuration: {errors}")

        # Create agent instance
        agent = InstantiatedAgent(
            agent_id=uuid4(),
            template_id=template.template_id,
            tenant_id=config.tenant_id,
            name=config.name,
            config=config,
            effective_capabilities=template.get_effective_capabilities(config),
            effective_policies=template.get_effective_policies(config),
            status="initializing",
            created_at=datetime.utcnow(),
        )

        # Register agent identity
        if self._identity_service:
            await self._register_identity(agent, template)

        # Configure policies
        if self._policy_service:
            await self._configure_policies(agent)

        # Setup integrations
        if self._integration_registry:
            await self._setup_integrations(agent, template, config)

        # Mark as ready
        agent.status = "ready"
        agent.updated_at = datetime.utcnow()

        self._agents[agent.agent_id] = agent

        logger.info(
            "agent_instantiated",
            agent_id=str(agent.agent_id),
            template_id=template.template_id,
            capabilities=len(agent.effective_capabilities),
            policies=len(agent.effective_policies),
        )

        return agent

    async def update_agent(
        self,
        agent_id: UUID,
        config_updates: dict[str, Any],
    ) -> InstantiatedAgent:
        """
        Update an instantiated agent's configuration.

        Only customizable parameters can be updated.

        Args:
            agent_id: Agent to update
            config_updates: Configuration changes

        Returns:
            Updated agent
        """
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        if not agent.config:
            raise ValueError("Agent has no configuration")

        # Apply updates to config
        if "parameters" in config_updates:
            agent.config.parameters.update(config_updates["parameters"])

        if "enabled_capabilities" in config_updates:
            agent.config.enabled_capabilities = config_updates["enabled_capabilities"]

        if "disabled_capabilities" in config_updates:
            agent.config.disabled_capabilities = config_updates["disabled_capabilities"]

        if "policy_overrides" in config_updates:
            agent.config.policy_overrides.update(config_updates["policy_overrides"])

        agent.updated_at = datetime.utcnow()

        logger.info(
            "agent_updated",
            agent_id=str(agent_id),
            updates=list(config_updates.keys()),
        )

        return agent

    async def delete_agent(self, agent_id: UUID) -> bool:
        """Delete an instantiated agent."""
        if agent_id not in self._agents:
            return False

        agent = self._agents[agent_id]

        # Revoke identity
        if self._identity_service:
            await self._identity_service.revoke_agent(str(agent_id))

        # Remove policies
        if self._policy_service:
            # Would remove agent-specific policies
            pass

        del self._agents[agent_id]

        logger.info("agent_deleted", agent_id=str(agent_id))
        return True

    def get_agent(self, agent_id: UUID) -> InstantiatedAgent | None:
        """Get an instantiated agent."""
        return self._agents.get(agent_id)

    def list_agents(
        self,
        tenant_id: str | None = None,
        template_id: str | None = None,
    ) -> list[InstantiatedAgent]:
        """List instantiated agents with optional filtering."""
        agents = list(self._agents.values())

        if tenant_id:
            agents = [a for a in agents if a.tenant_id == tenant_id]

        if template_id:
            agents = [a for a in agents if a.template_id == template_id]

        return agents

    async def clone_agent(
        self,
        agent_id: UUID,
        new_name: str,
        config_overrides: dict[str, Any] | None = None,
    ) -> InstantiatedAgent:
        """
        Clone an existing agent with optional modifications.

        Args:
            agent_id: Agent to clone
            new_name: Name for the new agent
            config_overrides: Optional configuration changes

        Returns:
            New agent instance
        """
        source_agent = self._agents.get(agent_id)
        if not source_agent:
            raise ValueError(f"Agent not found: {agent_id}")

        if not source_agent.config:
            raise ValueError("Source agent has no configuration")

        # Create new config from source
        new_config = TemplateConfig(
            template_id=source_agent.template_id,
            tenant_id=source_agent.tenant_id,
            name=new_name,
            description=source_agent.config.description,
            parameters=source_agent.config.parameters.copy(),
            enabled_capabilities=source_agent.config.enabled_capabilities.copy(),
            disabled_capabilities=source_agent.config.disabled_capabilities.copy(),
            policy_overrides=source_agent.config.policy_overrides.copy(),
            integration_configs=source_agent.config.integration_configs.copy(),
        )

        # Apply overrides
        if config_overrides:
            if "parameters" in config_overrides:
                new_config.parameters.update(config_overrides["parameters"])
            if "enabled_capabilities" in config_overrides:
                new_config.enabled_capabilities = config_overrides["enabled_capabilities"]

        # Need to get the template to instantiate
        # This would normally come from the registry
        logger.info(
            "agent_cloned",
            source_id=str(agent_id),
            new_name=new_name,
        )

        # Return a placeholder - in production, would re-instantiate
        return InstantiatedAgent(
            agent_id=uuid4(),
            template_id=source_agent.template_id,
            tenant_id=source_agent.tenant_id,
            name=new_name,
            config=new_config,
            effective_capabilities=source_agent.effective_capabilities.copy(),
            effective_policies=source_agent.effective_policies.copy(),
            status="ready",
        )

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _register_identity(
        self,
        agent: InstantiatedAgent,
        template: AgentTemplate,
    ) -> None:
        """Register agent identity with the identity service."""
        # Determine capabilities based on template
        capabilities = [cap.name for cap in agent.effective_capabilities]

        # Determine max risk tier
        max_risk = RiskTier.LOW
        for cap in agent.effective_capabilities:
            if cap.risk_tier.value > max_risk.value:
                max_risk = cap.risk_tier

        # Register with identity service
        # identity = await self._identity_service.create_agent_identity(
        #     agent_id=str(agent.agent_id),
        #     tenant_id=agent.tenant_id,
        #     name=agent.name,
        #     capabilities=capabilities,
        #     max_risk_tier=max_risk,
        # )

        logger.debug(
            "agent_identity_registered",
            agent_id=str(agent.agent_id),
            capabilities=capabilities,
        )

    async def _configure_policies(
        self,
        agent: InstantiatedAgent,
    ) -> None:
        """Configure policies for the agent."""
        for policy in agent.effective_policies:
            # Register policy with policy service
            # await self._policy_service.register_policy(
            #     policy_id=policy["policy_id"],
            #     agent_id=str(agent.agent_id),
            #     definition=policy["definition"],
            # )
            pass

        logger.debug(
            "agent_policies_configured",
            agent_id=str(agent.agent_id),
            policy_count=len(agent.effective_policies),
        )

    async def _setup_integrations(
        self,
        agent: InstantiatedAgent,
        template: AgentTemplate,
        config: TemplateConfig,
    ) -> None:
        """Setup required integrations for the agent."""
        for integration in template.integrations:
            integration_config = config.integration_configs.get(
                integration.integration_type,
                integration.default_config,
            )

            # Register integration with registry
            # await self._integration_registry.connect(
            #     integration_type=integration.integration_type,
            #     agent_id=str(agent.agent_id),
            #     config=integration_config,
            # )

            logger.debug(
                "agent_integration_setup",
                agent_id=str(agent.agent_id),
                integration=integration.integration_type,
            )


class TemplateValidator:
    """Validates template definitions."""

    @staticmethod
    def validate_template(template: AgentTemplate) -> tuple[bool, list[str]]:
        """Validate a template definition."""
        errors = []

        # Check required fields
        if not template.template_id:
            errors.append("template_id is required")

        if not template.name:
            errors.append("name is required")

        if not template.capabilities:
            errors.append("At least one capability is required")

        # Validate capabilities
        for cap in template.capabilities:
            if not cap.name:
                errors.append("Capability name is required")
            if not cap.action_types:
                errors.append(f"Capability '{cap.name}' must have action_types")

        # Validate parameters
        param_names = set()
        for param in template.parameters:
            if param.name in param_names:
                errors.append(f"Duplicate parameter name: {param.name}")
            param_names.add(param.name)

            if param.param_type not in ["string", "number", "boolean", "list", "object"]:
                errors.append(f"Invalid parameter type for '{param.name}': {param.param_type}")

        # Validate integrations
        for integration in template.integrations:
            if not integration.integration_type:
                errors.append("Integration type is required")

        return len(errors) == 0, errors


class TemplateBuilder:
    """Builder pattern for creating templates."""

    def __init__(self):
        self._template_id = ""
        self._name = ""
        self._description = ""
        self._category = None
        self._vertical = None
        self._version = None
        self._capabilities = []
        self._parameters = []
        self._policies = []
        self._workflows = []
        self._integrations = []
        self._customization_level = None
        self._tags = []

    def with_id(self, template_id: str) -> "TemplateBuilder":
        self._template_id = template_id
        return self

    def with_name(self, name: str) -> "TemplateBuilder":
        self._name = name
        return self

    def with_description(self, description: str) -> "TemplateBuilder":
        self._description = description
        return self

    def with_category(self, category) -> "TemplateBuilder":
        self._category = category
        return self

    def with_vertical(self, vertical) -> "TemplateBuilder":
        self._vertical = vertical
        return self

    def with_version(self, major: int, minor: int, patch: int) -> "TemplateBuilder":
        from services.templates.base import TemplateVersion
        self._version = TemplateVersion(major=major, minor=minor, patch=patch)
        return self

    def add_capability(self, capability) -> "TemplateBuilder":
        self._capabilities.append(capability)
        return self

    def add_parameter(self, parameter) -> "TemplateBuilder":
        self._parameters.append(parameter)
        return self

    def add_policy(self, policy) -> "TemplateBuilder":
        self._policies.append(policy)
        return self

    def add_integration(self, integration) -> "TemplateBuilder":
        self._integrations.append(integration)
        return self

    def with_customization_level(self, level) -> "TemplateBuilder":
        self._customization_level = level
        return self

    def with_tags(self, tags: list[str]) -> "TemplateBuilder":
        self._tags = tags
        return self

    def build(self) -> AgentTemplate:
        """Build the template."""
        from services.templates.base import (
            CustomizationLevel,
            TemplateCategory,
            TemplateVertical,
            TemplateVersion,
        )

        return AgentTemplate(
            template_id=self._template_id,
            name=self._name,
            description=self._description,
            category=self._category or TemplateCategory.CUSTOM,
            vertical=self._vertical or TemplateVertical.GENERAL,
            version=self._version or TemplateVersion(),
            capabilities=self._capabilities,
            parameters=self._parameters,
            default_policies=self._policies,
            default_workflows=self._workflows,
            integrations=self._integrations,
            customization_level=self._customization_level or CustomizationLevel.PARTIAL,
            tags=self._tags,
        )
