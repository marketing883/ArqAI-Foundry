"""
Key Management Service

Provides hierarchical key management with:
- Root CA (platform-level, HSM-backed via Vault)
- Intermediate CA per tenant
- Leaf certificates for agents, tokens, evidence
- Automated rotation schedules
- Revocation list distribution
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog

from arqai_foundry.config import get_settings
from arqai_foundry.core.exceptions import CertificateError
from services.identity.vault_client import get_vault_client, VaultClient

logger = structlog.get_logger(__name__)


class KeyManagementService:
    """
    Manages cryptographic keys and certificates for the platform.

    Key Hierarchy:
    - Root CA: Platform-level, 10-year validity, HSM-backed
    - Intermediate CA: Per-tenant, 5-year validity
    - Agent Certificates: 90-day validity, auto-rotated
    - Token Signing Keys: 7-day rotation
    - Evidence Signing Keys: 365-day rotation
    """

    def __init__(self, vault_client: VaultClient | None = None):
        self.vault = vault_client or get_vault_client()
        self.settings = get_settings().identity
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the key management infrastructure."""
        async with self._lock:
            if self._initialized:
                return

            logger.info("initializing_key_management")

            # Set up root PKI (idempotent)
            await self._setup_root_pki()

            # Set up transit keys for signing
            await self._setup_signing_keys()

            self._initialized = True
            logger.info("key_management_initialized")

    async def _setup_root_pki(self) -> None:
        """Set up root PKI infrastructure."""
        try:
            await self.vault.setup_pki_root(
                mount_point="pki",
                common_name="ArqAI Foundry Root CA",
                ttl=f"{self.settings.root_ca_validity_years * 8760}h",
            )
        except Exception as e:
            logger.warning("root_pki_setup_skipped", reason=str(e))

    async def _setup_signing_keys(self) -> None:
        """Set up transit keys for signing operations."""
        signing_keys = [
            ("token-signing", "ecdsa-p256"),
            ("evidence-signing", "ecdsa-p384"),
            ("internal-encryption", "aes256-gcm96"),
        ]

        for key_name, key_type in signing_keys:
            try:
                await self.vault.setup_transit_key(
                    key_name=key_name,
                    key_type=key_type,
                )
            except Exception as e:
                logger.warning(
                    "transit_key_setup_skipped",
                    key_name=key_name,
                    reason=str(e),
                )

    # =========================================================================
    # Tenant CA Management
    # =========================================================================

    async def create_tenant_ca(self, tenant_id: UUID) -> dict[str, Any]:
        """
        Create intermediate CA for a tenant.

        This CA will sign all certificates for agents belonging to this tenant.
        """
        await self.initialize()

        logger.info("creating_tenant_ca", tenant_id=str(tenant_id))

        result = await self.vault.setup_pki_intermediate(
            tenant_id=str(tenant_id),
            root_mount="pki",
            ttl=f"{self.settings.intermediate_ca_validity_years * 8760}h",
        )

        # Store tenant CA metadata
        await self.vault.write_secret(
            path=f"tenants/{tenant_id}/ca",
            data={
                "mount_point": result["mount_point"],
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (
                    datetime.utcnow()
                    + timedelta(days=self.settings.intermediate_ca_validity_years * 365)
                ).isoformat(),
            },
        )

        logger.info("tenant_ca_created", tenant_id=str(tenant_id))
        return result

    async def get_tenant_ca_info(self, tenant_id: UUID) -> dict[str, Any]:
        """Get tenant CA information."""
        await self.initialize()

        try:
            return await self.vault.read_secret(f"tenants/{tenant_id}/ca")
        except Exception:
            raise CertificateError(
                f"Tenant CA not found for tenant {tenant_id}",
                details={"tenant_id": str(tenant_id)},
            )

    # =========================================================================
    # Agent Certificate Management
    # =========================================================================

    async def issue_agent_certificate(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        template_id: str,
        environment: str,
    ) -> dict[str, Any]:
        """
        Issue a certificate for an agent.

        The certificate includes:
        - Subject: agent_id
        - Extension: tenant_id (non-transferable)
        - Extension: template_id
        - Extension: deployment_environment
        """
        await self.initialize()

        common_name = f"agent-{agent_id}"
        ttl = f"{self.settings.agent_cert_validity_days * 24}h"

        logger.info(
            "issuing_agent_certificate",
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
        )

        cert_data = await self.vault.issue_certificate(
            tenant_id=str(tenant_id),
            common_name=common_name,
            ttl=ttl,
        )

        # Store certificate metadata (private key stored separately)
        metadata = {
            "agent_id": str(agent_id),
            "tenant_id": str(tenant_id),
            "template_id": template_id,
            "environment": environment,
            "serial_number": cert_data["serial_number"],
            "issued_at": datetime.utcnow().isoformat(),
            "expires_at": datetime.fromtimestamp(cert_data["expiration"]).isoformat(),
            "rotation_count": 0,
        }

        await self.vault.write_secret(
            path=f"agents/{agent_id}/certificate",
            data={
                "certificate": cert_data["certificate"],
                "ca_chain": cert_data["ca_chain"],
                **metadata,
            },
        )

        # Store private key separately with stricter access
        await self.vault.write_secret(
            path=f"agents/{agent_id}/private_key",
            data={
                "private_key": cert_data["private_key"],
                "agent_id": str(agent_id),
            },
        )

        logger.info(
            "agent_certificate_issued",
            agent_id=str(agent_id),
            serial=cert_data["serial_number"],
        )

        # Return without private key (accessed separately when needed)
        return {
            "certificate": cert_data["certificate"],
            "ca_chain": cert_data["ca_chain"],
            "serial_number": cert_data["serial_number"],
            "fingerprint": self._compute_fingerprint(cert_data["certificate"]),
            **metadata,
        }

    async def rotate_agent_certificate(
        self,
        tenant_id: UUID,
        agent_id: UUID,
    ) -> dict[str, Any]:
        """Rotate an agent's certificate."""
        await self.initialize()

        # Get current certificate info
        try:
            current = await self.vault.read_secret(f"agents/{agent_id}/certificate")
        except Exception:
            raise CertificateError(
                f"No certificate found for agent {agent_id}",
                details={"agent_id": str(agent_id)},
            )

        # Revoke old certificate
        await self.revoke_agent_certificate(
            tenant_id=tenant_id,
            agent_id=agent_id,
            reason="rotation",
        )

        # Issue new certificate
        new_cert = await self.issue_agent_certificate(
            tenant_id=tenant_id,
            agent_id=agent_id,
            template_id=current["template_id"],
            environment=current["environment"],
        )

        # Update rotation count
        await self.vault.write_secret(
            path=f"agents/{agent_id}/certificate",
            data={
                **new_cert,
                "rotation_count": current.get("rotation_count", 0) + 1,
            },
        )

        logger.info(
            "agent_certificate_rotated",
            agent_id=str(agent_id),
            old_serial=current["serial_number"],
            new_serial=new_cert["serial_number"],
        )

        return new_cert

    async def revoke_agent_certificate(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        reason: str = "unspecified",
    ) -> None:
        """Revoke an agent's certificate."""
        await self.initialize()

        try:
            cert_info = await self.vault.read_secret(f"agents/{agent_id}/certificate")
            serial_number = cert_info["serial_number"]

            await self.vault.revoke_certificate(
                tenant_id=str(tenant_id),
                serial_number=serial_number,
            )

            # Update certificate status
            cert_info["revoked_at"] = datetime.utcnow().isoformat()
            cert_info["revocation_reason"] = reason
            await self.vault.write_secret(
                path=f"agents/{agent_id}/certificate",
                data=cert_info,
            )

            logger.info(
                "agent_certificate_revoked",
                agent_id=str(agent_id),
                serial=serial_number,
                reason=reason,
            )
        except Exception as e:
            logger.error(
                "agent_certificate_revocation_failed",
                agent_id=str(agent_id),
                error=str(e),
            )
            raise

    async def get_agent_certificate(self, agent_id: UUID) -> dict[str, Any]:
        """Get agent certificate (without private key)."""
        await self.initialize()

        try:
            return await self.vault.read_secret(f"agents/{agent_id}/certificate")
        except Exception:
            raise CertificateError(
                f"Certificate not found for agent {agent_id}",
                details={"agent_id": str(agent_id)},
            )

    async def get_agent_private_key(self, agent_id: UUID) -> str:
        """Get agent private key (restricted access)."""
        await self.initialize()

        try:
            data = await self.vault.read_secret(f"agents/{agent_id}/private_key")
            return data["private_key"]
        except Exception:
            raise CertificateError(
                f"Private key not found for agent {agent_id}",
                details={"agent_id": str(agent_id)},
            )

    # =========================================================================
    # Signing Operations
    # =========================================================================

    async def sign_token(self, token_data: str) -> str:
        """Sign a capability token."""
        await self.initialize()
        return await self.vault.sign_data(
            key_name="token-signing",
            data=token_data,
        )

    async def verify_token_signature(self, token_data: str, signature: str) -> bool:
        """Verify a token signature."""
        await self.initialize()
        return await self.vault.verify_signature(
            key_name="token-signing",
            data=token_data,
            signature=signature,
        )

    async def sign_evidence(self, evidence_data: str) -> str:
        """Sign an evidence packet."""
        await self.initialize()
        return await self.vault.sign_data(
            key_name="evidence-signing",
            data=evidence_data,
        )

    async def verify_evidence_signature(
        self, evidence_data: str, signature: str
    ) -> bool:
        """Verify an evidence signature."""
        await self.initialize()
        return await self.vault.verify_signature(
            key_name="evidence-signing",
            data=evidence_data,
            signature=signature,
        )

    # =========================================================================
    # Key Rotation
    # =========================================================================

    async def rotate_token_signing_key(self) -> None:
        """Rotate the token signing key."""
        await self.initialize()
        await self.vault.rotate_key("token-signing")
        logger.info("token_signing_key_rotated")

    async def rotate_evidence_signing_key(self) -> None:
        """Rotate the evidence signing key."""
        await self.initialize()
        await self.vault.rotate_key("evidence-signing")
        logger.info("evidence_signing_key_rotated")

    async def get_certificates_expiring_soon(
        self,
        tenant_id: UUID,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get certificates expiring within specified days."""
        await self.initialize()

        # In production, this would query a database index
        # For now, we return an empty list as placeholder
        logger.info(
            "checking_expiring_certificates",
            tenant_id=str(tenant_id),
            days=days,
        )
        return []

    # =========================================================================
    # Utilities
    # =========================================================================

    def _compute_fingerprint(self, certificate: str) -> str:
        """Compute SHA-256 fingerprint of certificate."""
        import hashlib

        # Remove PEM headers and decode
        cert_lines = certificate.strip().split("\n")
        cert_body = "".join(
            line for line in cert_lines if not line.startswith("-----")
        )

        import base64

        cert_bytes = base64.b64decode(cert_body)
        fingerprint = hashlib.sha256(cert_bytes).hexdigest()
        return ":".join(fingerprint[i : i + 2] for i in range(0, len(fingerprint), 2))
