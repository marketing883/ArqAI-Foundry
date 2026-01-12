"""
Base Integration Connector

Standard interface for all integrations with evidence enforcement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import structlog

from arqai_foundry.core.enums import IntegrationStatus
from arqai_foundry.core.models import CapabilityToken, IROperation

logger = structlog.get_logger(__name__)


@dataclass
class ConnectionStatus:
    """Status of an integration connection."""

    connected: bool
    status: IntegrationStatus
    last_check: datetime
    latency_ms: float | None = None
    error: str | None = None
    details: dict[str, Any] | None = None


@dataclass
class PermissionReport:
    """Report of integration permissions."""

    all_permissions_granted: bool
    required_permissions: list[str]
    granted_permissions: list[str]
    missing_permissions: list[str]
    checked_at: datetime


@dataclass
class ActionResult:
    """Result of an integration action."""

    success: bool
    action: str
    target: str
    pre_state: dict[str, Any]
    post_state: dict[str, Any]
    trace: list[dict[str, Any]]
    error: str | None = None
    execution_time_ms: float = 0.0


class IntegrationConnector(ABC):
    """
    Base class for all integration connectors.

    All integrations must:
    - Implement standard lifecycle methods
    - Enforce evidence generation for all actions
    - Capture pre/post state for audit
    - Support health checks
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._status = IntegrationStatus.DISCONNECTED
        self._last_health_check: datetime | None = None
        self._error_count = 0

    @property
    def name(self) -> str:
        """Integration name."""
        return self.__class__.__name__

    @property
    def status(self) -> IntegrationStatus:
        """Current connection status."""
        return self._status

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the external service.

        Returns True if connection successful.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the external service."""
        pass

    @abstractmethod
    async def test_connection(self) -> ConnectionStatus:
        """Test the connection and return status."""
        pass

    @abstractmethod
    async def test_permissions(self) -> PermissionReport:
        """Test that required permissions are granted."""
        pass

    # =========================================================================
    # Action Execution
    # =========================================================================

    @abstractmethod
    async def execute_action(
        self,
        action: IROperation,
        capability_token: CapabilityToken,
    ) -> ActionResult:
        """
        Execute an action with capability token.

        MUST:
        - Validate capability token
        - Capture pre-action state
        - Execute action
        - Capture post-action state
        - Generate evidence trace
        """
        pass

    @abstractmethod
    async def capture_pre_state(self, action: IROperation) -> dict[str, Any]:
        """Capture state before action execution."""
        pass

    @abstractmethod
    async def capture_post_state(self, action: IROperation) -> dict[str, Any]:
        """Capture state after action execution."""
        pass

    # =========================================================================
    # Query Operations
    # =========================================================================

    @abstractmethod
    async def query_resources(
        self,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Query resources with filters."""
        pass

    @abstractmethod
    async def get_resource_metadata(
        self,
        resource_id: str,
    ) -> dict[str, Any]:
        """Get metadata for a specific resource."""
        pass

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> ConnectionStatus:
        """Perform health check."""
        self._last_health_check = datetime.utcnow()
        return await self.test_connection()

    def get_health_status(self) -> dict[str, Any]:
        """Get current health status."""
        return {
            "status": self._status.value,
            "last_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "error_count": self._error_count,
        }

    # =========================================================================
    # Error Handling
    # =========================================================================

    def _record_error(self, error: str) -> None:
        """Record an error occurrence."""
        self._error_count += 1
        logger.error(
            "integration_error",
            integration=self.name,
            error=error,
            error_count=self._error_count,
        )

    def _reset_errors(self) -> None:
        """Reset error count after successful operation."""
        self._error_count = 0
