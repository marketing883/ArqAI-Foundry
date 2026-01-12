"""
Policy Store

Stores, versions, and queries policy rules efficiently.
Policies are immutable once created - updates create new versions.
"""

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from arqai_foundry.core.enums import Environment, PolicyEffect
from arqai_foundry.core.exceptions import PolicyError, PolicyNotFoundError
from arqai_foundry.core.models import Policy, PolicyRule

logger = structlog.get_logger(__name__)


# =============================================================================
# Default Policies
# =============================================================================

DEFAULT_COST_OPTIMIZATION_POLICY = {
    "policy_id": "cost-optimization-default",
    "version": "1.0.0",
    "name": "Default Cost Optimization Policy",
    "description": "Default policy for cost optimization actions",
    "jurisdiction": ["US", "EU"],
    "environments": ["development", "staging", "production"],
    "rules": [
        {
            "rule_id": "r1",
            "name": "prohibit_production_deletion",
            "priority": 100,
            "condition": {
                "and": [
                    {"field": "environment", "operator": "equals", "value": "production"},
                    {"field": "action", "operator": "in", "value": ["delete", "terminate"]},
                ]
            },
            "effect": "require_approval",
            "evidence_required": True,
            "approvers": [
                {"role": "platform_admin"},
                {"role": "engineering_director"},
            ],
            "timeout_hours": 24,
        },
        {
            "rule_id": "r2",
            "name": "require_approval_high_cost",
            "priority": 90,
            "condition": {
                "field": "monthly_cost_impact",
                "operator": "greater_than",
                "value": 5000,
            },
            "effect": "require_approval",
            "evidence_required": True,
            "approvers": [
                {"role": "finops_manager"},
                {"role": "engineering_director"},
            ],
            "timeout_hours": 24,
        },
        {
            "rule_id": "r3",
            "name": "auto_cleanup_completed_dev",
            "priority": 10,
            "condition": {
                "and": [
                    {"field": "environment", "operator": "equals", "value": "development"},
                    {"field": "project_status", "operator": "in", "value": ["completed", "cancelled"]},
                    {"field": "idle_days", "operator": "greater_than", "value": 90},
                    {"field": "risk_score", "operator": "less_than", "value": 30},
                ]
            },
            "effect": "allow_auto",
            "evidence_required": True,
        },
        {
            "rule_id": "r4",
            "name": "staging_requires_approval",
            "priority": 50,
            "condition": {
                "and": [
                    {"field": "environment", "operator": "equals", "value": "staging"},
                    {"field": "action", "operator": "in", "value": ["delete", "terminate"]},
                ]
            },
            "effect": "require_approval",
            "evidence_required": True,
            "approvers": [{"role": "team_lead"}],
            "timeout_hours": 48,
        },
        {
            "rule_id": "r5",
            "name": "default_allow_low_risk",
            "priority": 1,
            "condition": {
                "field": "risk_score",
                "operator": "less_than",
                "value": 30,
            },
            "effect": "allow_auto",
            "evidence_required": True,
        },
    ],
    "risk_scoring": {
        "factors": [
            {
                "name": "data_sensitivity",
                "weight": 0.35,
                "type": "mapping",
                "mapping": {
                    "public": 0,
                    "internal": 10,
                    "confidential": 25,
                    "pii": 40,
                    "phi": 50,
                },
            },
            {
                "name": "environment",
                "weight": 0.25,
                "type": "mapping",
                "mapping": {
                    "development": -15,
                    "staging": 0,
                    "production": 25,
                },
            },
            {
                "name": "financial_impact",
                "weight": 0.20,
                "type": "threshold",
                "thresholds": [
                    {"max": 1000, "score": 0},
                    {"max": 5000, "score": 10},
                    {"max": 10000, "score": 20},
                    {"max": float("inf"), "score": 30},
                ],
            },
            {
                "name": "idle_duration",
                "weight": 0.15,
                "type": "threshold",
                "thresholds": [
                    {"min": 180, "score": -50},
                    {"min": 90, "score": -30},
                    {"min": 30, "score": -10},
                    {"min": 0, "score": 0},
                ],
            },
            {
                "name": "has_dependencies",
                "weight": 0.05,
                "type": "boolean",
                "true_score": 20,
                "false_score": 0,
            },
        ],
    },
}

DEFAULT_HEALTHCARE_POLICY = {
    "policy_id": "healthcare-hipaa-default",
    "version": "1.0.0",
    "name": "HIPAA Compliance Policy",
    "description": "Policy for healthcare PHI access and operations",
    "jurisdiction": ["US"],
    "environments": ["development", "staging", "production"],
    "rules": [
        {
            "rule_id": "hipaa-1",
            "name": "phi_always_requires_approval",
            "priority": 100,
            "condition": {
                "field": "data_classification",
                "operator": "equals",
                "value": "phi",
            },
            "effect": "require_approval",
            "evidence_required": True,
            "approvers": [
                {"role": "privacy_officer"},
                {"role": "compliance_officer"},
            ],
            "timeout_hours": 4,
        },
        {
            "rule_id": "hipaa-2",
            "name": "phi_export_deny_without_authorization",
            "priority": 95,
            "condition": {
                "and": [
                    {"field": "data_classification", "operator": "equals", "value": "phi"},
                    {"field": "action", "operator": "equals", "value": "export"},
                    {"field": "authorization", "operator": "not_in", "value": ["treatment", "payment", "operations"]},
                ]
            },
            "effect": "deny",
            "evidence_required": True,
        },
        {
            "rule_id": "hipaa-3",
            "name": "phi_minimum_necessary",
            "priority": 90,
            "condition": {
                "and": [
                    {"field": "data_classification", "operator": "equals", "value": "phi"},
                    {"field": "minimum_necessary", "operator": "equals", "value": False},
                ]
            },
            "effect": "deny",
            "evidence_required": True,
        },
    ],
    "risk_scoring": {
        "factors": [
            {
                "name": "data_sensitivity",
                "weight": 0.50,
                "type": "mapping",
                "mapping": {
                    "public": 0,
                    "internal": 20,
                    "pii": 60,
                    "phi": 80,
                },
            },
            {
                "name": "authorization_type",
                "weight": 0.30,
                "type": "mapping",
                "mapping": {
                    "treatment": -20,
                    "payment": -10,
                    "operations": 0,
                    "research": 20,
                    "legal": 10,
                },
            },
            {
                "name": "de_identify",
                "weight": 0.20,
                "type": "boolean",
                "true_score": -30,
                "false_score": 0,
            },
        ],
    },
}


class PolicyStore:
    """
    Stores and manages policies with versioning.

    Policies are immutable - updates create new versions.
    Supports inheritance: tenant → workspace → agent
    """

    def __init__(self):
        # In-memory store (would use PostgreSQL in production)
        self._policies: dict[str, dict[str, Policy]] = {}  # policy_id -> version -> Policy
        self._tenant_policies: dict[UUID, list[str]] = {}  # tenant_id -> policy_ids
        self._active_versions: dict[str, str] = {}  # policy_id -> active_version

        # Load default policies
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default policies."""
        for policy_data in [DEFAULT_COST_OPTIMIZATION_POLICY, DEFAULT_HEALTHCARE_POLICY]:
            policy = self._parse_policy_data(policy_data, uuid4())
            self._store_policy(policy)

    def _parse_policy_data(
        self,
        data: dict[str, Any],
        tenant_id: UUID,
    ) -> Policy:
        """Parse policy data into Policy model."""
        rules = [
            PolicyRule(
                rule_id=r["rule_id"],
                name=r["name"],
                priority=r["priority"],
                condition=r["condition"],
                effect=PolicyEffect(r["effect"]),
                evidence_required=r.get("evidence_required", True),
                approvers=r.get("approvers", []),
                timeout_hours=r.get("timeout_hours", 24),
                delegation_allowed=r.get("delegation_allowed", False),
            )
            for r in data.get("rules", [])
        ]

        return Policy(
            policy_id=data["policy_id"],
            version=data["version"],
            tenant_id=tenant_id,
            name=data["name"],
            description=data.get("description"),
            jurisdiction=data.get("jurisdiction", []),
            environments=[Environment(e) for e in data.get("environments", [])],
            rules=rules,
            risk_scoring=data.get("risk_scoring", {}),
            created_by="system",
        )

    def _store_policy(self, policy: Policy) -> None:
        """Store a policy in the in-memory store."""
        if policy.policy_id not in self._policies:
            self._policies[policy.policy_id] = {}

        self._policies[policy.policy_id][policy.version] = policy
        self._active_versions[policy.policy_id] = policy.version

        # Track tenant policies
        if policy.tenant_id not in self._tenant_policies:
            self._tenant_policies[policy.tenant_id] = []
        if policy.policy_id not in self._tenant_policies[policy.tenant_id]:
            self._tenant_policies[policy.tenant_id].append(policy.policy_id)

    async def create_policy(
        self,
        tenant_id: UUID,
        policy_data: dict[str, Any],
        created_by: str,
    ) -> Policy:
        """Create a new policy."""
        policy_id = policy_data.get("policy_id", str(uuid4()))
        version = policy_data.get("version", "1.0.0")

        # Check if policy_id exists
        if policy_id in self._policies and version in self._policies[policy_id]:
            raise PolicyError(
                f"Policy version already exists: {policy_id} v{version}",
                details={"policy_id": policy_id, "version": version},
            )

        policy = self._parse_policy_data(policy_data, tenant_id)
        policy.created_by = created_by

        self._store_policy(policy)

        logger.info(
            "policy_created",
            policy_id=policy_id,
            version=version,
            tenant_id=str(tenant_id),
        )

        return policy

    async def get_policy(
        self,
        policy_id: str,
        version: str | None = None,
    ) -> Policy:
        """Get a policy by ID and optionally version."""
        if policy_id not in self._policies:
            raise PolicyNotFoundError(
                f"Policy not found: {policy_id}",
                details={"policy_id": policy_id},
            )

        versions = self._policies[policy_id]

        if version:
            if version not in versions:
                raise PolicyNotFoundError(
                    f"Policy version not found: {policy_id} v{version}",
                    details={"policy_id": policy_id, "version": version},
                )
            return versions[version]

        # Return active version
        active_version = self._active_versions.get(policy_id)
        if active_version and active_version in versions:
            return versions[active_version]

        # Return latest version
        latest = sorted(versions.keys(), reverse=True)[0]
        return versions[latest]

    async def update_policy(
        self,
        policy_id: str,
        policy_data: dict[str, Any],
        updated_by: str,
    ) -> Policy:
        """
        Update a policy by creating a new version.

        Policies are immutable - this creates a new version.
        """
        current = await self.get_policy(policy_id)

        # Increment version
        current_parts = current.version.split(".")
        new_minor = int(current_parts[1]) + 1
        new_version = f"{current_parts[0]}.{new_minor}.0"

        policy_data["policy_id"] = policy_id
        policy_data["version"] = new_version

        new_policy = self._parse_policy_data(policy_data, current.tenant_id)
        new_policy.created_by = updated_by

        self._store_policy(new_policy)

        logger.info(
            "policy_updated",
            policy_id=policy_id,
            old_version=current.version,
            new_version=new_version,
        )

        return new_policy

    async def list_policies(
        self,
        tenant_id: UUID | None = None,
    ) -> list[Policy]:
        """List policies, optionally filtered by tenant."""
        policies = []

        for policy_id, versions in self._policies.items():
            active_version = self._active_versions.get(policy_id)
            if active_version and active_version in versions:
                policy = versions[active_version]
                if tenant_id is None or policy.tenant_id == tenant_id:
                    policies.append(policy)

        return policies

    async def get_policy_versions(self, policy_id: str) -> list[str]:
        """Get all versions of a policy."""
        if policy_id not in self._policies:
            raise PolicyNotFoundError(
                f"Policy not found: {policy_id}",
                details={"policy_id": policy_id},
            )

        return sorted(self._policies[policy_id].keys(), reverse=True)

    async def set_active_version(
        self,
        policy_id: str,
        version: str,
    ) -> None:
        """Set the active version of a policy."""
        if policy_id not in self._policies:
            raise PolicyNotFoundError(f"Policy not found: {policy_id}")

        if version not in self._policies[policy_id]:
            raise PolicyNotFoundError(
                f"Policy version not found: {policy_id} v{version}"
            )

        self._active_versions[policy_id] = version

        logger.info(
            "policy_version_activated",
            policy_id=policy_id,
            version=version,
        )

    async def deactivate_policy(self, policy_id: str) -> None:
        """Deactivate a policy."""
        policy = await self.get_policy(policy_id)
        policy.is_active = False

        logger.warning(
            "policy_deactivated",
            policy_id=policy_id,
        )

    def compute_policy_hash(self, policy: Policy) -> str:
        """Compute deterministic hash of a policy."""
        policy_data = policy.model_dump(mode="json")
        # Remove non-deterministic fields
        policy_data.pop("created_at", None)
        policy_data.pop("updated_at", None)

        canonical = json.dumps(policy_data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def get_applicable_policies(
        self,
        tenant_id: UUID,
        environment: Environment,
        intent_type: str,
    ) -> list[Policy]:
        """Get policies applicable to a specific context."""
        all_policies = await self.list_policies(tenant_id)

        applicable = []
        for policy in all_policies:
            if not policy.is_active:
                continue

            # Check environment
            if policy.environments and environment not in policy.environments:
                continue

            # All checks passed
            applicable.append(policy)

        # Sort by specificity (more specific policies first)
        applicable.sort(key=lambda p: len(p.rules), reverse=True)

        return applicable
