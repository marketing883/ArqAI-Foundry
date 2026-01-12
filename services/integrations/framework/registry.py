"""
Integration Registry

Manages all registered integrations with lifecycle management.
"""

import asyncio
from datetime import datetime
from typing import Any, Type
from uuid import UUID, uuid4

import structlog

from arqai_foundry.core.enums import IntegrationStatus
from services.integrations.framework.base import (
    ConnectionStatus,
    IntegrationConnector,
    PermissionReport,
)

logger = structlog.get_logger(__name__)


class IntegrationRegistry:
    """
    Registry for managing integration connectors.

    Features:
    - Connector registration
    - Connection lifecycle management
    - Health monitoring
    - Permission validation
    """

    def __init__(self):
        # Registered connector types
        self._connector_types: dict[str, Type[IntegrationConnector]] = {}

        # Active connector instances by tenant
        self._instances: dict[UUID, dict[str, IntegrationConnector]] = {}

        # Health check task
        self._health_check_task: asyncio.Task | None = None
        self._health_check_interval = 60  # seconds

    def register_connector_type(
        self,
        name: str,
        connector_class: Type[IntegrationConnector],
    ) -> None:
        """Register a connector type."""
        self._connector_types[name] = connector_class
        logger.info("connector_type_registered", name=name)

    async def create_instance(
        self,
        tenant_id: UUID,
        connector_name: str,
        config: dict[str, Any],
        instance_id: str | None = None,
    ) -> IntegrationConnector:
        """Create a new connector instance for a tenant."""
        if connector_name not in self._connector_types:
            raise ValueError(f"Unknown connector type: {connector_name}")

        connector_class = self._connector_types[connector_name]
        instance = connector_class(config)
        instance_id = instance_id or f"{connector_name}-{uuid4().hex[:8]}"

        if tenant_id not in self._instances:
            self._instances[tenant_id] = {}

        self._instances[tenant_id][instance_id] = instance

        logger.info(
            "connector_instance_created",
            tenant_id=str(tenant_id),
            connector=connector_name,
            instance_id=instance_id,
        )

        return instance

    async def connect(
        self,
        tenant_id: UUID,
        instance_id: str,
    ) -> ConnectionStatus:
        """Connect a connector instance."""
        instance = self._get_instance(tenant_id, instance_id)

        try:
            success = await instance.connect()
            status = await instance.test_connection()
            return status
        except Exception as e:
            logger.error(
                "connector_connect_failed",
                tenant_id=str(tenant_id),
                instance_id=instance_id,
                error=str(e),
            )
            return ConnectionStatus(
                connected=False,
                status=IntegrationStatus.ERROR,
                last_check=datetime.utcnow(),
                error=str(e),
            )

    async def disconnect(
        self,
        tenant_id: UUID,
        instance_id: str,
    ) -> None:
        """Disconnect a connector instance."""
        instance = self._get_instance(tenant_id, instance_id)
        await instance.disconnect()

        logger.info(
            "connector_disconnected",
            tenant_id=str(tenant_id),
            instance_id=instance_id,
        )

    async def test_connection(
        self,
        tenant_id: UUID,
        instance_id: str,
    ) -> ConnectionStatus:
        """Test a connector's connection."""
        instance = self._get_instance(tenant_id, instance_id)
        return await instance.test_connection()

    async def test_permissions(
        self,
        tenant_id: UUID,
        instance_id: str,
    ) -> PermissionReport:
        """Test a connector's permissions."""
        instance = self._get_instance(tenant_id, instance_id)
        return await instance.test_permissions()

    def get_instance(
        self,
        tenant_id: UUID,
        instance_id: str,
    ) -> IntegrationConnector:
        """Get a connector instance."""
        return self._get_instance(tenant_id, instance_id)

    def list_instances(
        self,
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        """List all connector instances for a tenant."""
        instances = self._instances.get(tenant_id, {})
        return [
            {
                "instance_id": instance_id,
                "name": instance.name,
                "status": instance.status.value,
                "health": instance.get_health_status(),
            }
            for instance_id, instance in instances.items()
        ]

    def list_available_connectors(self) -> list[str]:
        """List all available connector types."""
        return list(self._connector_types.keys())

    async def remove_instance(
        self,
        tenant_id: UUID,
        instance_id: str,
    ) -> None:
        """Remove a connector instance."""
        instance = self._get_instance(tenant_id, instance_id)
        await instance.disconnect()
        del self._instances[tenant_id][instance_id]

        logger.info(
            "connector_instance_removed",
            tenant_id=str(tenant_id),
            instance_id=instance_id,
        )

    def _get_instance(
        self,
        tenant_id: UUID,
        instance_id: str,
    ) -> IntegrationConnector:
        """Get instance with validation."""
        tenant_instances = self._instances.get(tenant_id)
        if not tenant_instances:
            raise ValueError(f"No instances for tenant: {tenant_id}")

        instance = tenant_instances.get(instance_id)
        if not instance:
            raise ValueError(f"Instance not found: {instance_id}")

        return instance

    # =========================================================================
    # Health Monitoring
    # =========================================================================

    async def start_health_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._health_check_task is not None:
            return

        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("health_monitoring_started")

    async def stop_health_monitoring(self) -> None:
        """Stop background health monitoring."""
        if self._health_check_task:
            self._health_check_task.cancel()
            self._health_check_task = None
        logger.info("health_monitoring_stopped")

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while True:
            try:
                await asyncio.sleep(self._health_check_interval)
                await self._run_health_checks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("health_check_loop_error", error=str(e))

    async def _run_health_checks(self) -> None:
        """Run health checks on all instances."""
        for tenant_id, instances in self._instances.items():
            for instance_id, instance in instances.items():
                try:
                    await instance.health_check()
                except Exception as e:
                    logger.error(
                        "health_check_failed",
                        tenant_id=str(tenant_id),
                        instance_id=instance_id,
                        error=str(e),
                    )

    async def get_health_summary(self) -> dict[str, Any]:
        """Get health summary for all instances."""
        summary = {
            "total_instances": 0,
            "healthy": 0,
            "degraded": 0,
            "error": 0,
            "disconnected": 0,
        }

        for tenant_id, instances in self._instances.items():
            for instance_id, instance in instances.items():
                summary["total_instances"] += 1
                status = instance.status

                if status == IntegrationStatus.CONNECTED:
                    summary["healthy"] += 1
                elif status == IntegrationStatus.DEGRADED:
                    summary["degraded"] += 1
                elif status == IntegrationStatus.ERROR:
                    summary["error"] += 1
                else:
                    summary["disconnected"] += 1

        return summary
