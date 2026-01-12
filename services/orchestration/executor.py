"""
Action Executor

Executes validated actions against integrated systems with:
- Token validation
- Pre/post state capture
- Dry-run mode
- Rollback support
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from arqai_foundry.core.enums import ActionType
from arqai_foundry.core.exceptions import ExecutionError
from arqai_foundry.core.models import CapabilityToken, IROperation
from services.identity import CapabilityTokenService

logger = structlog.get_logger(__name__)


@dataclass
class ExecutionResult:
    """Result of an action execution."""

    success: bool
    pre_action_state: dict[str, Any]
    action_trace: list[dict[str, Any]]
    post_action_state: dict[str, Any]
    error: str | None = None
    rollback_available: bool = False
    execution_time_ms: float = 0.0


class ActionExecutor:
    """
    Executes validated actions with governance enforcement.

    Execution Modes:
    - Live: Actually execute the action
    - Dry-run: Simulate and report what would happen
    - Shadow: Monitor and suggest (no action)
    """

    def __init__(
        self,
        token_service: CapabilityTokenService | None = None,
    ):
        self.token_service = token_service or CapabilityTokenService()

        # Integration adapters
        self._adapters: dict[str, "IntegrationAdapter"] = {}

    def register_adapter(
        self,
        provider: str,
        adapter: "IntegrationAdapter",
    ) -> None:
        """Register an integration adapter."""
        self._adapters[provider] = adapter
        logger.info("adapter_registered", provider=provider)

    async def execute(
        self,
        operation: IROperation,
        token: CapabilityToken,
        mode: str = "live",  # live, dry_run, shadow
    ) -> ExecutionResult:
        """
        Execute an operation with the provided capability token.

        Steps:
        1. Validate token
        2. Capture pre-action state
        3. Execute action (or simulate)
        4. Verify action succeeded
        5. Capture post-action state
        """
        start_time = datetime.utcnow()

        logger.info(
            "execution_started",
            op_id=str(operation.op_id),
            op_type=operation.type,
            target=operation.target,
            mode=mode,
        )

        try:
            # Step 1: Validate and consume token
            await self.token_service.consume_token(
                token=token,
                expected_resource_id=operation.target,
                expected_action=self._get_action_type(operation.type),
            )

            # Get adapter for this operation
            adapter = self._get_adapter(operation)

            # Step 2: Capture pre-action state
            pre_state = await adapter.capture_state(operation.target)

            action_trace = []

            if mode == "live":
                # Step 3: Execute action
                trace_entry = await adapter.execute_action(operation)
                action_trace.append(trace_entry)

                # Step 4: Verify action succeeded
                if not trace_entry.get("success"):
                    raise ExecutionError(
                        f"Action failed: {trace_entry.get('error')}",
                        details={"trace": trace_entry},
                    )

            elif mode == "dry_run":
                # Simulate action
                trace_entry = await adapter.simulate_action(operation)
                trace_entry["mode"] = "dry_run"
                action_trace.append(trace_entry)

            elif mode == "shadow":
                # Just observe
                trace_entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "shadow_observation",
                    "recommendation": await adapter.get_recommendation(operation),
                    "mode": "shadow",
                }
                action_trace.append(trace_entry)

            # Step 5: Capture post-action state
            if mode == "live":
                post_state = await adapter.capture_state(operation.target)
            else:
                post_state = {"simulated": True, "expected_state": pre_state}

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = ExecutionResult(
                success=True,
                pre_action_state=pre_state,
                action_trace=action_trace,
                post_action_state=post_state,
                rollback_available=operation.rollback_supported,
                execution_time_ms=execution_time,
            )

            logger.info(
                "execution_completed",
                op_id=str(operation.op_id),
                success=True,
                mode=mode,
                execution_time_ms=execution_time,
            )

            return result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.error(
                "execution_failed",
                op_id=str(operation.op_id),
                error=str(e),
            )

            return ExecutionResult(
                success=False,
                pre_action_state={},
                action_trace=[{
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                }],
                post_action_state={},
                error=str(e),
                execution_time_ms=execution_time,
            )

    async def rollback(
        self,
        operation: IROperation,
        execution_result: ExecutionResult,
    ) -> ExecutionResult:
        """Rollback an executed operation."""
        if not execution_result.rollback_available:
            raise ExecutionError("Rollback not available for this operation")

        logger.info(
            "rollback_started",
            op_id=str(operation.op_id),
        )

        adapter = self._get_adapter(operation)

        try:
            # Execute rollback
            rollback_trace = await adapter.rollback(
                operation,
                execution_result.pre_action_state,
            )

            # Capture state after rollback
            post_rollback_state = await adapter.capture_state(operation.target)

            logger.info(
                "rollback_completed",
                op_id=str(operation.op_id),
            )

            return ExecutionResult(
                success=True,
                pre_action_state=execution_result.post_action_state,
                action_trace=[rollback_trace],
                post_action_state=post_rollback_state,
            )

        except Exception as e:
            logger.error(
                "rollback_failed",
                op_id=str(operation.op_id),
                error=str(e),
            )
            raise ExecutionError(f"Rollback failed: {e}")

    def _get_adapter(self, operation: IROperation) -> "IntegrationAdapter":
        """Get the appropriate adapter for an operation."""
        # Parse operation type to get provider
        # e.g., "cloud.aws.ec2.terminate" -> "aws"
        parts = operation.type.split(".")
        if len(parts) >= 2:
            provider = parts[1]
        else:
            provider = "default"

        adapter = self._adapters.get(provider)
        if not adapter:
            # Return mock adapter for development
            return MockAdapter()

        return adapter

    def _get_action_type(self, op_type: str) -> ActionType:
        """Extract action type from operation type string."""
        parts = op_type.split(".")
        action_str = parts[-1] if parts else "unknown"

        try:
            return ActionType(action_str)
        except ValueError:
            return ActionType.UPDATE


class IntegrationAdapter(ABC):
    """Base class for integration adapters."""

    @abstractmethod
    async def capture_state(self, resource_id: str) -> dict[str, Any]:
        """Capture current state of a resource."""
        pass

    @abstractmethod
    async def execute_action(self, operation: IROperation) -> dict[str, Any]:
        """Execute an action and return trace."""
        pass

    @abstractmethod
    async def simulate_action(self, operation: IROperation) -> dict[str, Any]:
        """Simulate an action and return expected result."""
        pass

    @abstractmethod
    async def rollback(
        self,
        operation: IROperation,
        previous_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Rollback an action."""
        pass

    async def get_recommendation(self, operation: IROperation) -> dict[str, Any]:
        """Get recommendation for an action (shadow mode)."""
        return {"recommendation": "Execute action", "confidence": 0.8}


class MockAdapter(IntegrationAdapter):
    """Mock adapter for development/testing."""

    async def capture_state(self, resource_id: str) -> dict[str, Any]:
        return {
            "resource_id": resource_id,
            "status": "running",
            "captured_at": datetime.utcnow().isoformat(),
        }

    async def execute_action(self, operation: IROperation) -> dict[str, Any]:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "action": operation.type,
            "target": operation.target,
            "success": True,
            "message": "Mock execution successful",
        }

    async def simulate_action(self, operation: IROperation) -> dict[str, Any]:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "action": operation.type,
            "target": operation.target,
            "simulated": True,
            "expected_outcome": "success",
        }

    async def rollback(
        self,
        operation: IROperation,
        previous_state: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "action": "rollback",
            "target": operation.target,
            "restored_state": previous_state,
            "success": True,
        }
