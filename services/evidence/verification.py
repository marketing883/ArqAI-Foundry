"""
Public Verification Service

Allows anyone to verify evidence integrity without revealing sensitive data.
No authentication required for verification.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import structlog

from arqai_foundry.config import get_settings
from arqai_foundry.core.exceptions import EvidenceError
from services.evidence.vault import EvidenceVault

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Simple rate limiter for verification requests."""

    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed."""
        now = time.time()
        minute_ago = now - 60

        # Clean old entries
        self._requests[client_ip] = [
            ts for ts in self._requests[client_ip]
            if ts > minute_ago
        ]

        # Check limit
        if len(self._requests[client_ip]) >= self.requests_per_minute:
            return False

        # Record request
        self._requests[client_ip].append(now)
        return True

    def get_retry_after(self, client_ip: str) -> int:
        """Get seconds until next request is allowed."""
        if client_ip not in self._requests or not self._requests[client_ip]:
            return 0

        oldest = min(self._requests[client_ip])
        retry_after = int(oldest + 60 - time.time())
        return max(0, retry_after)


class PublicVerificationService:
    """
    Public service for verifying evidence integrity.

    Key Properties:
    - No authentication required
    - No sensitive metadata disclosed
    - Rate limited to prevent abuse
    - Tamper detection
    """

    def __init__(
        self,
        vault: EvidenceVault | None = None,
    ):
        self.vault = vault or EvidenceVault()
        self.settings = get_settings().evidence

        self.rate_limiter = RateLimiter(
            requests_per_minute=self.settings.public_rate_limit_per_minute
        )

        # Verification stats
        self._verification_count = 0
        self._valid_count = 0
        self._invalid_count = 0

    async def verify(
        self,
        evidence_id: UUID,
        client_ip: str = "unknown",
    ) -> dict[str, Any]:
        """
        Verify evidence integrity (public endpoint).

        Returns verification result with NO sensitive metadata.
        """
        start_time = time.time()

        # Check rate limit
        if not self.rate_limiter.is_allowed(client_ip):
            retry_after = self.rate_limiter.get_retry_after(client_ip)
            logger.warning(
                "rate_limit_exceeded",
                client_ip=client_ip,
                retry_after=retry_after,
            )
            return {
                "error": "rate_limit_exceeded",
                "retry_after_seconds": retry_after,
            }

        self._verification_count += 1

        try:
            # Perform verification
            result = await self.vault.verify_evidence(evidence_id)

            # Get public metadata only
            try:
                public_data = await self.vault.get_evidence_public(evidence_id)
            except Exception:
                public_data = {}

            verification_time = (time.time() - start_time) * 1000

            if result["valid"]:
                self._valid_count += 1
            else:
                self._invalid_count += 1

            response = {
                "evidence_id": str(evidence_id),
                "valid": result["valid"],
                "verified_at": datetime.utcnow().isoformat(),
                "hash_verified": result["hash_verified"],
                "signature_verified": result["signature_verified"],
                "chain_verified": result["chain_verified"],
                "verification_time_ms": round(verification_time, 2),
                # Public metadata only (no tenant/agent IDs)
                "schema_version": public_data.get("schema_version"),
                "timestamp_hour": public_data.get("timestamp_hour"),
                "evidence_hash": public_data.get("evidence_hash"),
                # NO tenant_id, agent_id, or detailed content
            }

            logger.info(
                "public_verification_completed",
                evidence_id=str(evidence_id),
                valid=result["valid"],
                verification_time_ms=verification_time,
            )

            return response

        except Exception as e:
            logger.error(
                "public_verification_failed",
                evidence_id=str(evidence_id),
                error=str(e),
            )
            return {
                "evidence_id": str(evidence_id),
                "valid": False,
                "error": "verification_failed",
                "verified_at": datetime.utcnow().isoformat(),
            }

    async def verify_batch(
        self,
        evidence_ids: list[UUID],
        client_ip: str = "unknown",
    ) -> dict[str, Any]:
        """Verify multiple evidence packets."""
        results = []

        for eid in evidence_ids[:10]:  # Max 10 per batch
            result = await self.verify(eid, client_ip)
            results.append(result)

            # Check rate limit after each verification
            if "error" in result and result.get("error") == "rate_limit_exceeded":
                break

        return {
            "results": results,
            "total_requested": len(evidence_ids),
            "total_verified": len(results),
        }

    async def get_verification_status(
        self,
        evidence_id: UUID,
    ) -> dict[str, Any]:
        """Get quick verification status without full verification."""
        try:
            public_data = await self.vault.get_evidence_public(evidence_id)
            return {
                "exists": True,
                "evidence_id": str(evidence_id),
                "evidence_hash": public_data.get("evidence_hash"),
                "timestamp_hour": public_data.get("timestamp_hour"),
            }
        except Exception:
            return {
                "exists": False,
                "evidence_id": str(evidence_id),
            }

    async def get_chain_status(self) -> dict[str, Any]:
        """Get public chain status information."""
        head = await self.vault.get_chain_head()

        return {
            "chain_length": head.get("block_number", 0),
            "last_block_time": head.get("timestamp"),
            "status": "healthy" if not head.get("empty") else "empty",
        }

    def get_stats(self) -> dict[str, Any]:
        """Get verification statistics."""
        return {
            "total_verifications": self._verification_count,
            "valid_count": self._valid_count,
            "invalid_count": self._invalid_count,
            "validity_rate": (
                self._valid_count / self._verification_count * 100
                if self._verification_count > 0 else 0
            ),
        }
