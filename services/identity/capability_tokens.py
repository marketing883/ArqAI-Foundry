"""
Capability Token Service

Provides single-use, time-bound, scoped authorization tokens:
- Token structure with resource_id, action, constraints
- Token validation (signature, expiry, nonce, scope)
- Token revocation
- Token usage tracking
"""

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import structlog

from arqai_foundry.config import get_settings
from arqai_foundry.core.enums import ActionType
from arqai_foundry.core.exceptions import (
    TokenAlreadyUsedError,
    TokenError,
    TokenExpiredError,
    TokenRevokedError,
    TokenScopeMismatchError,
)
from arqai_foundry.core.models import CapabilityToken
from services.identity.key_management import KeyManagementService

logger = structlog.get_logger(__name__)


class CapabilityTokenService:
    """
    Issues and validates single-use, time-bound, scoped authorization tokens.

    Every agent action requires a valid capability token that:
    - Is signed by the platform
    - Has not expired
    - Has not been used before (single-use)
    - Matches the action being performed
    """

    def __init__(
        self,
        key_management: KeyManagementService | None = None,
    ):
        self.key_mgmt = key_management or KeyManagementService()
        self.settings = get_settings().identity

        # Track used nonces (would use Redis in production)
        self._used_nonces: set[str] = set()

        # Track revoked tokens
        self._revoked_tokens: set[UUID] = set()

    async def issue_token(
        self,
        agent_identity: str,  # Certificate fingerprint
        resource_id: str,
        action: ActionType,
        constraints: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> CapabilityToken:
        """
        Issue a capability token for a specific action.

        The token authorizes exactly one action on one resource.
        """
        if ttl_seconds is None:
            ttl_seconds = self.settings.capability_token_default_ttl_seconds

        # Enforce maximum TTL
        if ttl_seconds > self.settings.capability_token_max_ttl_seconds:
            ttl_seconds = self.settings.capability_token_max_ttl_seconds
            logger.warning(
                "token_ttl_capped",
                requested_ttl=ttl_seconds,
                max_ttl=self.settings.capability_token_max_ttl_seconds,
            )

        token_id = uuid4()
        issued_at = datetime.utcnow()
        expires_at = issued_at + timedelta(seconds=ttl_seconds)
        one_time_nonce = secrets.token_urlsafe(32)

        # Create token data for signing
        token_data = {
            "token_id": str(token_id),
            "agent_identity": agent_identity,
            "resource_id": resource_id,
            "action": action.value,
            "constraints": constraints or {},
            "issued_at": issued_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "one_time_nonce": one_time_nonce,
        }

        # Sign token
        signature = await self._sign_token(token_data)

        token = CapabilityToken(
            token_id=token_id,
            agent_identity=agent_identity,
            resource_id=resource_id,
            action=action,
            constraints=constraints or {},
            issued_at=issued_at,
            expires_at=expires_at,
            one_time_nonce=one_time_nonce,
            signature=signature,
        )

        logger.info(
            "capability_token_issued",
            token_id=str(token_id),
            resource_id=resource_id,
            action=action.value,
            ttl_seconds=ttl_seconds,
        )

        return token

    async def validate_token(
        self,
        token: CapabilityToken,
        expected_resource_id: str | None = None,
        expected_action: ActionType | None = None,
        expected_agent_identity: str | None = None,
    ) -> bool:
        """
        Validate a capability token.

        Checks:
        1. Signature is valid
        2. Token has not expired
        3. Token has not been used (nonce check)
        4. Token has not been revoked
        5. Agent identity matches (if provided)
        6. Resource and action match (if provided)

        This does NOT consume the token - use consume_token() for that.
        """
        start_time = datetime.utcnow()

        try:
            # Check if revoked
            if token.token_id in self._revoked_tokens:
                logger.warning(
                    "token_validation_failed",
                    token_id=str(token.token_id),
                    reason="revoked",
                )
                raise TokenRevokedError(
                    "Token has been revoked",
                    details={"token_id": str(token.token_id)},
                )

            # Check expiry
            now = datetime.utcnow()
            if now >= token.expires_at:
                logger.warning(
                    "token_validation_failed",
                    token_id=str(token.token_id),
                    reason="expired",
                )
                raise TokenExpiredError(
                    "Token has expired",
                    details={
                        "token_id": str(token.token_id),
                        "expired_at": token.expires_at.isoformat(),
                    },
                )

            # Check if already used
            if token.one_time_nonce in self._used_nonces:
                logger.warning(
                    "token_validation_failed",
                    token_id=str(token.token_id),
                    reason="already_used",
                )
                raise TokenAlreadyUsedError(
                    "Token has already been used",
                    details={"token_id": str(token.token_id)},
                )

            # Verify signature
            token_data = self._token_to_signing_data(token)
            is_valid = await self.key_mgmt.verify_token_signature(
                token_data=json.dumps(token_data, sort_keys=True),
                signature=token.signature,
            )

            if not is_valid:
                logger.warning(
                    "token_validation_failed",
                    token_id=str(token.token_id),
                    reason="invalid_signature",
                )
                raise TokenError(
                    "Token signature is invalid",
                    details={"token_id": str(token.token_id)},
                )

            # Check scope
            if expected_agent_identity and token.agent_identity != expected_agent_identity:
                logger.warning(
                    "token_validation_failed",
                    token_id=str(token.token_id),
                    reason="agent_mismatch",
                )
                raise TokenScopeMismatchError(
                    "Token agent identity does not match",
                    details={
                        "token_id": str(token.token_id),
                        "expected": expected_agent_identity,
                        "actual": token.agent_identity,
                    },
                )

            if expected_resource_id and token.resource_id != expected_resource_id:
                logger.warning(
                    "token_validation_failed",
                    token_id=str(token.token_id),
                    reason="resource_mismatch",
                )
                raise TokenScopeMismatchError(
                    "Token resource does not match",
                    details={
                        "token_id": str(token.token_id),
                        "expected": expected_resource_id,
                        "actual": token.resource_id,
                    },
                )

            if expected_action and token.action != expected_action:
                logger.warning(
                    "token_validation_failed",
                    token_id=str(token.token_id),
                    reason="action_mismatch",
                )
                raise TokenScopeMismatchError(
                    "Token action does not match",
                    details={
                        "token_id": str(token.token_id),
                        "expected": expected_action.value,
                        "actual": token.action.value,
                    },
                )

            validation_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.debug(
                "token_validated",
                token_id=str(token.token_id),
                validation_time_ms=validation_time,
            )

            return True

        except (TokenExpiredError, TokenRevokedError, TokenAlreadyUsedError, TokenScopeMismatchError):
            raise
        except Exception as e:
            logger.error(
                "token_validation_error",
                token_id=str(token.token_id),
                error=str(e),
            )
            return False

    async def consume_token(
        self,
        token: CapabilityToken,
        expected_resource_id: str | None = None,
        expected_action: ActionType | None = None,
        expected_agent_identity: str | None = None,
    ) -> bool:
        """
        Validate and consume a capability token.

        After consumption, the token cannot be used again.
        """
        # Validate first
        await self.validate_token(
            token=token,
            expected_resource_id=expected_resource_id,
            expected_action=expected_action,
            expected_agent_identity=expected_agent_identity,
        )

        # Mark as used
        self._used_nonces.add(token.one_time_nonce)
        token.used_at = datetime.utcnow()

        logger.info(
            "capability_token_consumed",
            token_id=str(token.token_id),
            resource_id=token.resource_id,
            action=token.action.value,
        )

        return True

    async def revoke_token(
        self,
        token_id: UUID,
        reason: str = "manual_revocation",
    ) -> None:
        """
        Revoke a capability token immediately.

        Used for:
        - Anomaly detection
        - Policy changes
        - Workflow cancellation
        """
        self._revoked_tokens.add(token_id)

        logger.warning(
            "capability_token_revoked",
            token_id=str(token_id),
            reason=reason,
        )

    async def revoke_tokens_for_agent(
        self,
        agent_identity: str,
        reason: str = "agent_suspended",
    ) -> int:
        """
        Revoke all tokens for a specific agent.

        Used when an agent's identity is suspended or revoked.
        """
        # In production, this would query a database to find all tokens
        # for the agent and revoke them
        logger.warning(
            "agent_tokens_revoked",
            agent_identity=agent_identity,
            reason=reason,
        )
        return 0

    async def get_token_info(self, token_id: UUID) -> dict[str, Any] | None:
        """Get information about a token (for audit purposes)."""
        is_revoked = token_id in self._revoked_tokens

        return {
            "token_id": str(token_id),
            "revoked": is_revoked,
        }

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _token_to_signing_data(self, token: CapabilityToken) -> dict[str, Any]:
        """Convert token to data structure for signing/verification."""
        return {
            "token_id": str(token.token_id),
            "agent_identity": token.agent_identity,
            "resource_id": token.resource_id,
            "action": token.action.value,
            "constraints": token.constraints,
            "issued_at": token.issued_at.isoformat(),
            "expires_at": token.expires_at.isoformat(),
            "one_time_nonce": token.one_time_nonce,
        }

    async def _sign_token(self, token_data: dict[str, Any]) -> str:
        """Sign token data."""
        data_str = json.dumps(token_data, sort_keys=True)
        return await self.key_mgmt.sign_token(data_str)


class TokenScope:
    """Helper class for defining token scope."""

    def __init__(
        self,
        resource_id: str,
        action: ActionType,
        constraints: dict[str, Any] | None = None,
    ):
        self.resource_id = resource_id
        self.action = action
        self.constraints = constraints or {}

    @classmethod
    def for_ec2_terminate(
        cls,
        instance_id: str,
        require_snapshot: bool = True,
    ) -> "TokenScope":
        """Create scope for EC2 instance termination."""
        return cls(
            resource_id=instance_id,
            action=ActionType.TERMINATE,
            constraints={
                "require_snapshot": require_snapshot,
                "provider": "aws",
                "resource_type": "ec2",
            },
        )

    @classmethod
    def for_ec2_stop(cls, instance_id: str) -> "TokenScope":
        """Create scope for EC2 instance stop."""
        return cls(
            resource_id=instance_id,
            action=ActionType.STOP,
            constraints={
                "provider": "aws",
                "resource_type": "ec2",
            },
        )

    @classmethod
    def for_rds_stop(cls, db_instance_id: str) -> "TokenScope":
        """Create scope for RDS instance stop."""
        return cls(
            resource_id=db_instance_id,
            action=ActionType.STOP,
            constraints={
                "provider": "aws",
                "resource_type": "rds",
            },
        )

    @classmethod
    def for_read_only(cls, resource_id: str) -> "TokenScope":
        """Create scope for read-only access."""
        return cls(
            resource_id=resource_id,
            action=ActionType.READ,
            constraints={
                "read_only": True,
            },
        )
