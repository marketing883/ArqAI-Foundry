"""
Agent Identity Service

Provides cryptographic identity management for agent instances:
- Unique keypair per agent deployment
- Identity binding to agent_id, tenant_id, template_id
- Identity lifecycle (issue, rotate, revoke, suspend)
- Runtime attestation
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import structlog

from arqai_foundry.config import get_settings
from arqai_foundry.core.enums import AgentStatus, Environment
from arqai_foundry.core.exceptions import (
    IdentityError,
    IdentityNotFoundError,
    IdentitySuspendedError,
)
from arqai_foundry.core.models import AgentIdentity
from services.identity.key_management import KeyManagementService
from services.identity.vault_client import get_vault_client

logger = structlog.get_logger(__name__)


class AgentIdentityService:
    """
    Manages cryptographic identities for agent instances.

    Every agent must have a valid identity to execute any action.
    Identities are cryptographically bound to their tenant and template.
    """

    def __init__(
        self,
        key_management: KeyManagementService | None = None,
    ):
        self.key_mgmt = key_management or KeyManagementService()
        self.vault = get_vault_client()
        self.settings = get_settings().identity

        # In-memory cache for identity validation (backed by Redis in production)
        self._identity_cache: dict[UUID, AgentIdentity] = {}

    async def create_identity(
        self,
        tenant_id: UUID,
        template_id: str,
        environment: Environment,
        agent_name: str | None = None,
    ) -> AgentIdentity:
        """
        Create a new agent identity.

        This generates:
        - Unique agent_id
        - X.509 certificate from tenant's CA
        - Identity record in the registry
        """
        agent_id = uuid4()

        logger.info(
            "creating_agent_identity",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
            template_id=template_id,
        )

        # Issue certificate from tenant CA
        cert_data = await self.key_mgmt.issue_agent_certificate(
            tenant_id=tenant_id,
            agent_id=agent_id,
            template_id=template_id,
            environment=environment.value,
        )

        # Calculate expiration
        expires_at = datetime.utcnow() + timedelta(
            days=self.settings.agent_cert_validity_days
        )

        # Create identity record
        identity = AgentIdentity(
            agent_id=agent_id,
            tenant_id=tenant_id,
            template_id=template_id,
            deployment_environment=environment,
            certificate_fingerprint=cert_data["fingerprint"],
            public_key=cert_data["certificate"],
            issued_at=datetime.utcnow(),
            expires_at=expires_at,
            issuer=f"ArqAI Tenant {tenant_id} Intermediate CA",
        )

        # Store identity record
        await self._store_identity(identity)

        # Cache identity
        self._identity_cache[agent_id] = identity

        logger.info(
            "agent_identity_created",
            agent_id=str(agent_id),
            fingerprint=cert_data["fingerprint"],
        )

        return identity

    async def get_identity(self, agent_id: UUID) -> AgentIdentity:
        """Get an agent's identity."""
        # Check cache first
        if agent_id in self._identity_cache:
            identity = self._identity_cache[agent_id]
            if identity.is_valid:
                return identity

        # Load from storage
        identity = await self._load_identity(agent_id)

        if identity is None:
            raise IdentityNotFoundError(
                f"Identity not found for agent {agent_id}",
                details={"agent_id": str(agent_id)},
            )

        if identity.suspended_at is not None:
            raise IdentitySuspendedError(
                f"Identity suspended for agent {agent_id}",
                details={
                    "agent_id": str(agent_id),
                    "suspended_at": identity.suspended_at.isoformat(),
                    "reason": identity.suspension_reason,
                },
            )

        # Update cache
        self._identity_cache[agent_id] = identity

        return identity

    async def validate_identity(
        self,
        agent_id: UUID,
        certificate_fingerprint: str | None = None,
    ) -> bool:
        """
        Validate an agent's identity.

        Checks:
        - Identity exists
        - Identity is active
        - Identity is not expired
        - Identity is not suspended
        - Certificate fingerprint matches (if provided)
        """
        try:
            identity = await self.get_identity(agent_id)

            if not identity.is_valid:
                logger.warning(
                    "identity_validation_failed",
                    agent_id=str(agent_id),
                    reason="invalid_state",
                )
                return False

            if certificate_fingerprint:
                if identity.certificate_fingerprint != certificate_fingerprint:
                    logger.warning(
                        "identity_validation_failed",
                        agent_id=str(agent_id),
                        reason="fingerprint_mismatch",
                    )
                    return False

            # Update last activity
            identity.last_activity_at = datetime.utcnow()
            await self._store_identity(identity)

            return True

        except (IdentityNotFoundError, IdentitySuspendedError):
            return False

    async def rotate_identity(self, agent_id: UUID) -> AgentIdentity:
        """
        Rotate an agent's identity (new certificate, same agent_id).

        This is used for:
        - Scheduled rotation (every 90 days)
        - Manual rotation after suspected compromise
        """
        identity = await self.get_identity(agent_id)

        logger.info(
            "rotating_agent_identity",
            agent_id=str(agent_id),
            current_fingerprint=identity.certificate_fingerprint,
        )

        # Rotate certificate
        cert_data = await self.key_mgmt.rotate_agent_certificate(
            tenant_id=identity.tenant_id,
            agent_id=agent_id,
        )

        # Update identity
        identity.certificate_fingerprint = cert_data["fingerprint"]
        identity.public_key = cert_data["certificate"]
        identity.issued_at = datetime.utcnow()
        identity.expires_at = datetime.utcnow() + timedelta(
            days=self.settings.agent_cert_validity_days
        )
        identity.rotation_count += 1

        await self._store_identity(identity)
        self._identity_cache[agent_id] = identity

        logger.info(
            "agent_identity_rotated",
            agent_id=str(agent_id),
            new_fingerprint=cert_data["fingerprint"],
            rotation_count=identity.rotation_count,
        )

        return identity

    async def suspend_identity(
        self,
        agent_id: UUID,
        reason: str,
    ) -> AgentIdentity:
        """
        Suspend an agent's identity.

        Used for:
        - Policy violations
        - Security incidents
        - Administrative action
        """
        identity = await self.get_identity(agent_id)

        logger.warning(
            "suspending_agent_identity",
            agent_id=str(agent_id),
            reason=reason,
        )

        identity.is_active = False
        identity.suspended_at = datetime.utcnow()
        identity.suspension_reason = reason

        await self._store_identity(identity)
        self._identity_cache[agent_id] = identity

        # Revoke certificate
        await self.key_mgmt.revoke_agent_certificate(
            tenant_id=identity.tenant_id,
            agent_id=agent_id,
            reason=f"suspended: {reason}",
        )

        logger.warning(
            "agent_identity_suspended",
            agent_id=str(agent_id),
            reason=reason,
        )

        return identity

    async def reinstate_identity(
        self,
        agent_id: UUID,
    ) -> AgentIdentity:
        """
        Reinstate a suspended identity.

        This issues a new certificate and clears suspension.
        """
        try:
            identity = await self._load_identity(agent_id)
        except Exception:
            raise IdentityNotFoundError(
                f"Identity not found for agent {agent_id}",
                details={"agent_id": str(agent_id)},
            )

        if identity.suspended_at is None:
            raise IdentityError(
                f"Identity is not suspended for agent {agent_id}",
                details={"agent_id": str(agent_id)},
            )

        logger.info(
            "reinstating_agent_identity",
            agent_id=str(agent_id),
        )

        # Issue new certificate
        cert_data = await self.key_mgmt.issue_agent_certificate(
            tenant_id=identity.tenant_id,
            agent_id=agent_id,
            template_id=identity.template_id,
            environment=identity.deployment_environment.value,
        )

        # Update identity
        identity.is_active = True
        identity.suspended_at = None
        identity.suspension_reason = None
        identity.certificate_fingerprint = cert_data["fingerprint"]
        identity.public_key = cert_data["certificate"]
        identity.issued_at = datetime.utcnow()
        identity.expires_at = datetime.utcnow() + timedelta(
            days=self.settings.agent_cert_validity_days
        )

        await self._store_identity(identity)
        self._identity_cache[agent_id] = identity

        logger.info(
            "agent_identity_reinstated",
            agent_id=str(agent_id),
            new_fingerprint=cert_data["fingerprint"],
        )

        return identity

    async def revoke_identity(
        self,
        agent_id: UUID,
        reason: str = "terminated",
    ) -> None:
        """
        Permanently revoke an agent's identity.

        Used when an agent is terminated/deleted.
        """
        try:
            identity = await self._load_identity(agent_id)
        except Exception:
            logger.warning(
                "identity_revocation_skipped",
                agent_id=str(agent_id),
                reason="not_found",
            )
            return

        logger.info(
            "revoking_agent_identity",
            agent_id=str(agent_id),
            reason=reason,
        )

        # Revoke certificate
        await self.key_mgmt.revoke_agent_certificate(
            tenant_id=identity.tenant_id,
            agent_id=agent_id,
            reason=reason,
        )

        # Remove from cache
        self._identity_cache.pop(agent_id, None)

        # Mark as revoked in storage
        identity.is_active = False
        identity.suspended_at = datetime.utcnow()
        identity.suspension_reason = f"revoked: {reason}"
        await self._store_identity(identity)

        logger.info(
            "agent_identity_revoked",
            agent_id=str(agent_id),
            reason=reason,
        )

    async def list_identities(
        self,
        tenant_id: UUID,
        include_suspended: bool = False,
    ) -> list[AgentIdentity]:
        """List all agent identities for a tenant."""
        # In production, this queries a database
        # For now, return cached identities
        identities = [
            identity
            for identity in self._identity_cache.values()
            if identity.tenant_id == tenant_id
        ]

        if not include_suspended:
            identities = [i for i in identities if i.suspended_at is None]

        return identities

    async def get_identities_expiring_soon(
        self,
        tenant_id: UUID,
        days: int = 30,
    ) -> list[AgentIdentity]:
        """Get identities expiring within specified days."""
        threshold = datetime.utcnow() + timedelta(days=days)

        identities = await self.list_identities(tenant_id)
        return [
            identity
            for identity in identities
            if identity.expires_at <= threshold
        ]

    # =========================================================================
    # Storage Operations (would use database in production)
    # =========================================================================

    async def _store_identity(self, identity: AgentIdentity) -> None:
        """Store identity record."""
        await self.vault.write_secret(
            path=f"agents/{identity.agent_id}/identity",
            data=identity.model_dump(mode="json"),
        )

    async def _load_identity(self, agent_id: UUID) -> AgentIdentity:
        """Load identity record."""
        data = await self.vault.read_secret(f"agents/{agent_id}/identity")
        return AgentIdentity.model_validate(data)
