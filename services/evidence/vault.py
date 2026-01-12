"""
Evidence Vault

Append-only ledger for immutable, cryptographically signed audit evidence.
"""

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from arqai_foundry.config import get_settings
from arqai_foundry.core.exceptions import (
    EvidenceChainError,
    EvidenceError,
    EvidenceNotFoundError,
)
from arqai_foundry.core.models import EvidencePacket
from services.identity.key_management import KeyManagementService

logger = structlog.get_logger(__name__)


class EvidenceVault:
    """
    Append-only ledger for evidence packets.

    Key Properties:
    - Immutable: evidence cannot be modified or deleted
    - Hash-chained: each evidence links to previous
    - Signed: all evidence cryptographically signed
    - Verifiable: public verification of integrity
    """

    def __init__(
        self,
        key_management: KeyManagementService | None = None,
    ):
        self.key_mgmt = key_management or KeyManagementService()
        self.settings = get_settings().evidence

        # In-memory ledger (would use PostgreSQL in production)
        self._ledger: list[EvidencePacket] = []
        self._by_id: dict[UUID, EvidencePacket] = {}
        self._by_tenant: dict[UUID, list[UUID]] = {}
        self._by_agent: dict[UUID, list[UUID]] = {}

        # Block number counter
        self._next_block = 1

    async def create_evidence(
        self,
        tenant_id: UUID,
        agent_id: UUID,
        request: dict[str, Any],
        compliance_ir: dict[str, Any],
        policy_validation: dict[str, Any],
        risk_assessment: dict[str, Any],
        capability_token: dict[str, Any],
        execution: dict[str, Any],
        financial_impact: dict[str, float] | None = None,
    ) -> EvidencePacket:
        """
        Create a new evidence packet.

        This is an atomic operation - evidence is either fully created
        or not created at all.
        """
        evidence_id = uuid4()
        timestamp = datetime.utcnow()

        logger.info(
            "creating_evidence",
            evidence_id=str(evidence_id),
            tenant_id=str(tenant_id),
            agent_id=str(agent_id),
        )

        # Get previous hash for chain
        previous_hash = self._get_previous_hash()

        # Build evidence content
        evidence_content = {
            "evidence_id": str(evidence_id),
            "schema_version": "2.0",
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "timestamp": timestamp.isoformat(),
            "request": request,
            "compliance_ir": compliance_ir,
            "policy_validation": policy_validation,
            "risk_assessment": risk_assessment,
            "capability_token": self._redact_token(capability_token),
            "execution": execution,
            "financial_impact": financial_impact,
            "previous_hash": previous_hash,
            "block_number": self._next_block,
        }

        # Compute hash
        evidence_hash = self._compute_hash(evidence_content)

        # Sign evidence
        signature = await self._sign_evidence(evidence_hash)

        # Create packet
        packet = EvidencePacket(
            evidence_id=evidence_id,
            schema_version="2.0",
            evidence_hash=evidence_hash,
            signature=signature,
            verification_url=f"https://verify.arqai.com/evidence/{evidence_id}",
            tenant_id=tenant_id,
            agent_id=agent_id,
            timestamp=timestamp,
            request=request,
            compliance_ir=compliance_ir,
            policy_validation=policy_validation,
            risk_assessment=risk_assessment,
            capability_token=self._redact_token(capability_token),
            execution=execution,
            financial_impact=financial_impact,
            previous_hash=previous_hash,
            block_number=self._next_block,
        )

        # Append to ledger (atomic)
        self._append_to_ledger(packet)

        logger.info(
            "evidence_created",
            evidence_id=str(evidence_id),
            block_number=packet.block_number,
            evidence_hash=evidence_hash[:16],
        )

        return packet

    def _get_previous_hash(self) -> str | None:
        """Get the hash of the previous evidence packet."""
        if not self._ledger:
            return None
        return self._ledger[-1].evidence_hash

    def _compute_hash(self, content: dict[str, Any]) -> str:
        """Compute SHA-256 hash of evidence content."""
        # Exclude hash and signature from hash computation
        hashable_content = {
            k: v for k, v in content.items()
            if k not in ["evidence_hash", "signature"]
        }
        canonical = json.dumps(hashable_content, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"

    async def _sign_evidence(self, evidence_hash: str) -> str:
        """Sign the evidence hash."""
        return await self.key_mgmt.sign_evidence(evidence_hash)

    def _redact_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Redact sensitive fields from capability token."""
        redacted = dict(token)
        # Redact the signature to prevent token reuse
        if "signature" in redacted:
            redacted["signature"] = "[REDACTED]"
        if "one_time_nonce" in redacted:
            redacted["one_time_nonce"] = "[REDACTED]"
        return redacted

    def _append_to_ledger(self, packet: EvidencePacket) -> None:
        """Append evidence to ledger (atomic operation)."""
        # Add to main ledger
        self._ledger.append(packet)
        self._by_id[packet.evidence_id] = packet
        self._next_block += 1

        # Index by tenant
        if packet.tenant_id not in self._by_tenant:
            self._by_tenant[packet.tenant_id] = []
        self._by_tenant[packet.tenant_id].append(packet.evidence_id)

        # Index by agent
        if packet.agent_id not in self._by_agent:
            self._by_agent[packet.agent_id] = []
        self._by_agent[packet.agent_id].append(packet.evidence_id)

    async def get_evidence(
        self,
        evidence_id: UUID,
        tenant_id: UUID | None = None,
    ) -> EvidencePacket:
        """
        Get evidence by ID.

        If tenant_id is provided, verifies the evidence belongs to that tenant.
        """
        packet = self._by_id.get(evidence_id)

        if not packet:
            raise EvidenceNotFoundError(
                f"Evidence not found: {evidence_id}",
                details={"evidence_id": str(evidence_id)},
            )

        # Verify tenant access
        if tenant_id and packet.tenant_id != tenant_id:
            raise EvidenceNotFoundError(
                f"Evidence not found: {evidence_id}",
                details={"evidence_id": str(evidence_id)},
            )

        return packet

    async def get_evidence_public(
        self,
        evidence_id: UUID,
    ) -> dict[str, Any]:
        """
        Get public view of evidence (no sensitive metadata).

        This is for public verification.
        """
        packet = await self.get_evidence(evidence_id)

        return {
            "evidence_id": str(packet.evidence_id),
            "schema_version": packet.schema_version,
            "evidence_hash": packet.evidence_hash,
            "timestamp_hour": packet.timestamp.replace(
                minute=0, second=0, microsecond=0
            ).isoformat(),
            "block_number": packet.block_number,
            "verification_url": packet.verification_url,
        }

    async def verify_evidence(
        self,
        evidence_id: UUID,
    ) -> dict[str, Any]:
        """
        Verify evidence integrity.

        Checks:
        1. Hash matches content
        2. Signature is valid
        3. Chain link is valid
        """
        packet = await self.get_evidence(evidence_id)

        # Recompute hash
        content = {
            "evidence_id": str(packet.evidence_id),
            "schema_version": packet.schema_version,
            "tenant_id": str(packet.tenant_id),
            "agent_id": str(packet.agent_id),
            "timestamp": packet.timestamp.isoformat(),
            "request": packet.request,
            "compliance_ir": packet.compliance_ir,
            "policy_validation": packet.policy_validation,
            "risk_assessment": packet.risk_assessment,
            "capability_token": packet.capability_token,
            "execution": packet.execution,
            "financial_impact": packet.financial_impact,
            "previous_hash": packet.previous_hash,
            "block_number": packet.block_number,
        }
        computed_hash = self._compute_hash(content)
        hash_valid = computed_hash == packet.evidence_hash

        # Verify signature
        signature_valid = await self.key_mgmt.verify_evidence_signature(
            packet.evidence_hash,
            packet.signature,
        )

        # Verify chain
        chain_valid = True
        if packet.previous_hash:
            # Find previous packet
            prev_idx = packet.block_number - 2  # 0-indexed
            if 0 <= prev_idx < len(self._ledger):
                prev_packet = self._ledger[prev_idx]
                chain_valid = prev_packet.evidence_hash == packet.previous_hash
            else:
                chain_valid = False

        return {
            "evidence_id": str(evidence_id),
            "valid": hash_valid and signature_valid and chain_valid,
            "hash_verified": hash_valid,
            "signature_verified": signature_valid,
            "chain_verified": chain_valid,
            "verified_at": datetime.utcnow().isoformat(),
        }

    async def verify_chain(
        self,
        start_block: int = 1,
        end_block: int | None = None,
    ) -> dict[str, Any]:
        """Verify integrity of evidence chain."""
        if end_block is None:
            end_block = len(self._ledger)

        errors: list[dict[str, Any]] = []
        verified_count = 0

        for i in range(start_block - 1, min(end_block, len(self._ledger))):
            packet = self._ledger[i]

            # Verify hash
            verification = await self.verify_evidence(packet.evidence_id)

            if not verification["valid"]:
                errors.append({
                    "block_number": packet.block_number,
                    "evidence_id": str(packet.evidence_id),
                    "hash_valid": verification["hash_verified"],
                    "signature_valid": verification["signature_verified"],
                    "chain_valid": verification["chain_verified"],
                })
            else:
                verified_count += 1

        return {
            "valid": len(errors) == 0,
            "blocks_checked": end_block - start_block + 1,
            "blocks_verified": verified_count,
            "errors": errors,
            "verified_at": datetime.utcnow().isoformat(),
        }

    async def list_evidence(
        self,
        tenant_id: UUID,
        agent_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[EvidencePacket]:
        """List evidence with filters."""
        # Get candidate evidence IDs
        if agent_id:
            evidence_ids = self._by_agent.get(agent_id, [])
        else:
            evidence_ids = self._by_tenant.get(tenant_id, [])

        # Filter and paginate
        results: list[EvidencePacket] = []
        for eid in evidence_ids:
            packet = self._by_id.get(eid)
            if not packet:
                continue

            # Apply date filters
            if start_date and packet.timestamp < start_date:
                continue
            if end_date and packet.timestamp > end_date:
                continue

            results.append(packet)

        # Sort by timestamp descending
        results.sort(key=lambda p: p.timestamp, reverse=True)

        # Paginate
        return results[offset : offset + limit]

    async def get_evidence_count(
        self,
        tenant_id: UUID,
        agent_id: UUID | None = None,
    ) -> int:
        """Get count of evidence packets."""
        if agent_id:
            return len(self._by_agent.get(agent_id, []))
        return len(self._by_tenant.get(tenant_id, []))

    async def get_chain_head(self) -> dict[str, Any]:
        """Get information about the chain head."""
        if not self._ledger:
            return {
                "empty": True,
                "block_number": 0,
            }

        head = self._ledger[-1]
        return {
            "empty": False,
            "block_number": head.block_number,
            "evidence_id": str(head.evidence_id),
            "evidence_hash": head.evidence_hash,
            "timestamp": head.timestamp.isoformat(),
        }
