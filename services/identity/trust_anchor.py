"""
Trust Anchor Registry

Maintains root of trust and public key infrastructure:
- Platform root CA certificate (public)
- Intermediate CA registry per tenant
- Public key lookup service
- Certificate transparency log
"""

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from arqai_foundry.config import get_settings
from arqai_foundry.core.exceptions import CertificateError
from services.identity.vault_client import get_vault_client

logger = structlog.get_logger(__name__)


class TrustAnchorRegistry:
    """
    Maintains the root of trust for the platform.

    Provides:
    - Public access to root CA certificate
    - Tenant CA registry (authenticated access)
    - Public key lookup by evidence_id (for public verification)
    - Certificate transparency log
    """

    def __init__(self):
        self.vault = get_vault_client()
        self.settings = get_settings()

        # Cache for root CA (rarely changes)
        self._root_ca_cache: dict[str, Any] | None = None

        # Certificate transparency log (would use database in production)
        self._transparency_log: list[dict[str, Any]] = []

    # =========================================================================
    # Root CA Operations
    # =========================================================================

    async def get_root_ca_certificate(self) -> dict[str, Any]:
        """
        Get the platform root CA certificate.

        This is public information used for certificate chain verification.
        """
        if self._root_ca_cache:
            return self._root_ca_cache

        try:
            # In production, this would be stored in a well-known location
            client = await self.vault._get_client()
            response = client.secrets.pki.read_ca_certificate(mount_point="pki")

            self._root_ca_cache = {
                "certificate": response,
                "issuer": "ArqAI Foundry Root CA",
                "subject": "ArqAI Foundry Root CA",
                "not_before": datetime.utcnow().isoformat(),  # Would parse from cert
                "not_after": datetime.utcnow().isoformat(),  # Would parse from cert
            }

            return self._root_ca_cache

        except Exception as e:
            logger.error("root_ca_fetch_failed", error=str(e))
            raise CertificateError(f"Failed to fetch root CA: {e}")

    async def get_root_ca_chain(self) -> list[str]:
        """Get the full certificate chain from root CA."""
        root_ca = await self.get_root_ca_certificate()
        return [root_ca["certificate"]]

    # =========================================================================
    # Tenant CA Registry
    # =========================================================================

    async def register_tenant_ca(
        self,
        tenant_id: UUID,
        certificate: str,
        mount_point: str,
    ) -> None:
        """Register a tenant's intermediate CA."""
        await self.vault.write_secret(
            path=f"trust-anchors/tenants/{tenant_id}",
            data={
                "tenant_id": str(tenant_id),
                "certificate": certificate,
                "mount_point": mount_point,
                "registered_at": datetime.utcnow().isoformat(),
                "is_active": True,
            },
        )

        # Log to transparency log
        await self._log_certificate_event(
            event_type="tenant_ca_registered",
            tenant_id=tenant_id,
            certificate=certificate,
        )

        logger.info(
            "tenant_ca_registered",
            tenant_id=str(tenant_id),
        )

    async def get_tenant_ca(self, tenant_id: UUID) -> dict[str, Any]:
        """
        Get a tenant's intermediate CA certificate.

        Requires authentication - only tenant members can access.
        """
        try:
            return await self.vault.read_secret(
                f"trust-anchors/tenants/{tenant_id}"
            )
        except Exception:
            raise CertificateError(
                f"Tenant CA not found for tenant {tenant_id}",
                details={"tenant_id": str(tenant_id)},
            )

    async def list_tenant_cas(self) -> list[dict[str, Any]]:
        """List all registered tenant CAs (admin only)."""
        # In production, this would query a database
        return []

    async def revoke_tenant_ca(
        self,
        tenant_id: UUID,
        reason: str,
    ) -> None:
        """Revoke a tenant's CA (emergency use only)."""
        try:
            ca_info = await self.get_tenant_ca(tenant_id)
            ca_info["is_active"] = False
            ca_info["revoked_at"] = datetime.utcnow().isoformat()
            ca_info["revocation_reason"] = reason

            await self.vault.write_secret(
                path=f"trust-anchors/tenants/{tenant_id}",
                data=ca_info,
            )

            await self._log_certificate_event(
                event_type="tenant_ca_revoked",
                tenant_id=tenant_id,
                reason=reason,
            )

            logger.warning(
                "tenant_ca_revoked",
                tenant_id=str(tenant_id),
                reason=reason,
            )
        except Exception as e:
            logger.error(
                "tenant_ca_revocation_failed",
                tenant_id=str(tenant_id),
                error=str(e),
            )
            raise

    # =========================================================================
    # Public Key Lookup
    # =========================================================================

    async def lookup_public_key_by_evidence(
        self,
        evidence_id: UUID,
    ) -> dict[str, Any]:
        """
        Look up the public key used to sign an evidence packet.

        This is a PUBLIC endpoint - no authentication required.
        Returns only the public key, no other metadata.
        """
        try:
            # Look up evidence to get the signing key reference
            evidence_key_ref = await self.vault.read_secret(
                f"evidence-keys/{evidence_id}"
            )

            return {
                "evidence_id": str(evidence_id),
                "public_key": evidence_key_ref["public_key"],
                "algorithm": evidence_key_ref.get("algorithm", "ECDSA-P384"),
            }
        except Exception:
            raise CertificateError(
                f"Public key not found for evidence {evidence_id}",
                details={"evidence_id": str(evidence_id)},
            )

    async def lookup_public_key_by_agent(
        self,
        agent_id: UUID,
        tenant_id: UUID,  # Required for authorization
    ) -> dict[str, Any]:
        """
        Look up the public key for an agent.

        Requires authentication - only tenant members can access.
        """
        try:
            cert_info = await self.vault.read_secret(
                f"agents/{agent_id}/certificate"
            )

            # Verify tenant match
            if cert_info.get("tenant_id") != str(tenant_id):
                raise CertificateError(
                    "Agent does not belong to tenant",
                    details={
                        "agent_id": str(agent_id),
                        "tenant_id": str(tenant_id),
                    },
                )

            return {
                "agent_id": str(agent_id),
                "public_key": cert_info["certificate"],
                "fingerprint": cert_info.get("fingerprint"),
                "expires_at": cert_info.get("expires_at"),
            }
        except CertificateError:
            raise
        except Exception:
            raise CertificateError(
                f"Public key not found for agent {agent_id}",
                details={"agent_id": str(agent_id)},
            )

    # =========================================================================
    # Certificate Transparency Log
    # =========================================================================

    async def _log_certificate_event(
        self,
        event_type: str,
        tenant_id: UUID | None = None,
        agent_id: UUID | None = None,
        certificate: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Log a certificate event to the transparency log."""
        import hashlib

        event = {
            "event_id": len(self._transparency_log) + 1,
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "tenant_id": str(tenant_id) if tenant_id else None,
            "agent_id": str(agent_id) if agent_id else None,
            "certificate_hash": (
                hashlib.sha256(certificate.encode()).hexdigest()
                if certificate else None
            ),
            "reason": reason,
        }

        # Compute hash chain
        if self._transparency_log:
            previous_hash = self._transparency_log[-1].get("event_hash", "")
        else:
            previous_hash = "genesis"

        import json
        event_data = json.dumps(event, sort_keys=True)
        event["previous_hash"] = previous_hash
        event["event_hash"] = hashlib.sha256(
            (previous_hash + event_data).encode()
        ).hexdigest()

        self._transparency_log.append(event)

        logger.debug(
            "certificate_transparency_event",
            event_type=event_type,
            event_id=event["event_id"],
        )

    async def get_transparency_log(
        self,
        start_index: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Get entries from the certificate transparency log.

        This is PUBLIC - anyone can audit certificate operations.
        """
        return self._transparency_log[start_index : start_index + limit]

    async def verify_transparency_log_integrity(self) -> dict[str, Any]:
        """
        Verify the integrity of the transparency log.

        Checks that the hash chain is intact.
        """
        import hashlib
        import json

        if not self._transparency_log:
            return {
                "valid": True,
                "entries_checked": 0,
            }

        previous_hash = "genesis"
        for i, event in enumerate(self._transparency_log):
            # Recompute hash
            event_copy = {k: v for k, v in event.items() if k not in ["previous_hash", "event_hash"]}
            event_data = json.dumps(event_copy, sort_keys=True)
            expected_hash = hashlib.sha256(
                (previous_hash + event_data).encode()
            ).hexdigest()

            if event.get("event_hash") != expected_hash:
                return {
                    "valid": False,
                    "error": f"Hash mismatch at index {i}",
                    "entries_checked": i + 1,
                }

            previous_hash = event["event_hash"]

        return {
            "valid": True,
            "entries_checked": len(self._transparency_log),
            "latest_hash": previous_hash,
        }

    # =========================================================================
    # Key Pinning
    # =========================================================================

    async def get_pinned_keys(self) -> dict[str, str]:
        """
        Get pinned public keys for critical services.

        These keys are used for additional validation of
        communication with critical platform services.
        """
        return {
            "api_gateway": "",  # Would be populated with actual keys
            "policy_engine": "",
            "evidence_vault": "",
        }

    async def verify_service_key(
        self,
        service_name: str,
        public_key: str,
    ) -> bool:
        """Verify a service's public key against pinned keys."""
        pinned_keys = await self.get_pinned_keys()
        expected_key = pinned_keys.get(service_name)

        if not expected_key:
            logger.warning(
                "no_pinned_key_for_service",
                service_name=service_name,
            )
            return True  # Allow if no pin configured

        return public_key == expected_key
