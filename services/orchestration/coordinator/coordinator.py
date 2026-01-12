"""
Agent Coordinator

Coordinates multi-agent workflows with:
- Sequential handoff
- Parallel execution
- Consensus-based decisions
- Conflict resolution
- Shared state management
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

import structlog

from arqai_foundry.core.exceptions import AgentError, OrchestrationError
from arqai_foundry.core.models import AgentMessage, SharedState
from services.orchestration.message_bus.bus import MessageBus

logger = structlog.get_logger(__name__)


class WorkflowStepType(str, Enum):
    """Types of workflow steps."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    CONSENSUS = "consensus"
    SUPERVISOR = "supervisor"


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    """A single step in a workflow."""

    step_id: str
    step_type: WorkflowStepType
    agent_ids: list[UUID]
    handler: str  # Handler method name
    next_steps: list[str] = field(default_factory=list)
    condition: dict[str, Any] | None = None
    consensus_rule: str | None = None  # "all_must_approve", "majority", "any"
    timeout_seconds: float = 300.0


@dataclass
class Workflow:
    """Multi-agent workflow definition."""

    workflow_id: UUID
    name: str
    tenant_id: UUID
    steps: list[WorkflowStep]
    entry_step: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WorkflowExecution:
    """Execution state of a workflow."""

    execution_id: UUID
    workflow_id: UUID
    tenant_id: UUID
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: str | None = None
    step_results: dict[str, Any] = field(default_factory=dict)
    shared_state: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class AgentCoordinator:
    """
    Coordinates multi-agent workflows.

    Supports coordination patterns:
    - Sequential: Agent A → Agent B → Agent C
    - Parallel: Agent A, B, C run simultaneously
    - Conditional: Branch based on results
    - Consensus: Agents must agree before proceeding
    - Supervisor: Parent agent delegates to child agents
    """

    def __init__(
        self,
        message_bus: MessageBus | None = None,
    ):
        self.message_bus = message_bus or MessageBus()

        # Registered workflows
        self._workflows: dict[UUID, Workflow] = {}

        # Active executions
        self._executions: dict[UUID, WorkflowExecution] = {}

        # Shared state store
        self._shared_state: dict[UUID, dict[str, SharedState]] = {}

        # Agent handlers for workflow steps
        self._step_handlers: dict[str, Callable] = {}

    def register_workflow(self, workflow: Workflow) -> None:
        """Register a workflow definition."""
        self._workflows[workflow.workflow_id] = workflow
        logger.info(
            "workflow_registered",
            workflow_id=str(workflow.workflow_id),
            name=workflow.name,
        )

    def register_step_handler(
        self,
        handler_name: str,
        handler: Callable[[dict[str, Any], dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]],
    ) -> None:
        """Register a handler function for workflow steps."""
        self._step_handlers[handler_name] = handler
        logger.debug("step_handler_registered", handler_name=handler_name)

    async def start_workflow(
        self,
        workflow_id: UUID,
        input_data: dict[str, Any],
        tenant_id: UUID,
    ) -> WorkflowExecution:
        """Start a workflow execution."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise OrchestrationError(f"Workflow not found: {workflow_id}")

        execution_id = uuid4()
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            status=WorkflowStatus.RUNNING,
            current_step=workflow.entry_step,
            started_at=datetime.utcnow(),
            shared_state={"input": input_data},
        )

        self._executions[execution_id] = execution
        self._shared_state[execution_id] = {}

        logger.info(
            "workflow_started",
            execution_id=str(execution_id),
            workflow_id=str(workflow_id),
            entry_step=workflow.entry_step,
        )

        # Start execution
        asyncio.create_task(self._execute_workflow(execution, workflow))

        return execution

    async def _execute_workflow(
        self,
        execution: WorkflowExecution,
        workflow: Workflow,
    ) -> None:
        """Execute the workflow steps."""
        try:
            current_step_id = execution.current_step

            while current_step_id:
                step = self._find_step(workflow, current_step_id)
                if not step:
                    raise OrchestrationError(f"Step not found: {current_step_id}")

                execution.current_step = current_step_id
                logger.info(
                    "executing_step",
                    execution_id=str(execution.execution_id),
                    step_id=current_step_id,
                    step_type=step.step_type.value,
                )

                # Execute step based on type
                if step.step_type == WorkflowStepType.SEQUENTIAL:
                    result = await self._execute_sequential(execution, step)
                elif step.step_type == WorkflowStepType.PARALLEL:
                    result = await self._execute_parallel(execution, step)
                elif step.step_type == WorkflowStepType.CONSENSUS:
                    result = await self._execute_consensus(execution, step)
                elif step.step_type == WorkflowStepType.CONDITIONAL:
                    result = await self._execute_conditional(execution, step)
                elif step.step_type == WorkflowStepType.SUPERVISOR:
                    result = await self._execute_supervisor(execution, step)
                else:
                    raise OrchestrationError(f"Unknown step type: {step.step_type}")

                # Store result
                execution.step_results[current_step_id] = result

                # Determine next step
                current_step_id = self._determine_next_step(step, result, execution)

            # Workflow completed
            execution.status = WorkflowStatus.COMPLETED
            execution.completed_at = datetime.utcnow()
            logger.info(
                "workflow_completed",
                execution_id=str(execution.execution_id),
            )

        except Exception as e:
            execution.status = WorkflowStatus.FAILED
            execution.error = str(e)
            execution.completed_at = datetime.utcnow()
            logger.error(
                "workflow_failed",
                execution_id=str(execution.execution_id),
                error=str(e),
            )

    async def _execute_sequential(
        self,
        execution: WorkflowExecution,
        step: WorkflowStep,
    ) -> dict[str, Any]:
        """Execute agents sequentially."""
        results = []

        for agent_id in step.agent_ids:
            handler = self._step_handlers.get(step.handler)
            if not handler:
                raise OrchestrationError(f"Handler not found: {step.handler}")

            context = {
                "agent_id": str(agent_id),
                "execution_id": str(execution.execution_id),
                "shared_state": execution.shared_state,
                "previous_results": results,
            }

            result = await asyncio.wait_for(
                handler(context, execution.shared_state),
                timeout=step.timeout_seconds,
            )
            results.append({"agent_id": str(agent_id), "result": result})

            # Update shared state with result
            execution.shared_state[f"step_{step.step_id}_{agent_id}"] = result

        return {"type": "sequential", "results": results}

    async def _execute_parallel(
        self,
        execution: WorkflowExecution,
        step: WorkflowStep,
    ) -> dict[str, Any]:
        """Execute agents in parallel."""
        handler = self._step_handlers.get(step.handler)
        if not handler:
            raise OrchestrationError(f"Handler not found: {step.handler}")

        tasks = []
        for agent_id in step.agent_ids:
            context = {
                "agent_id": str(agent_id),
                "execution_id": str(execution.execution_id),
                "shared_state": execution.shared_state,
            }
            task = asyncio.create_task(handler(context, execution.shared_state))
            tasks.append((agent_id, task))

        results = []
        for agent_id, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=step.timeout_seconds)
                results.append({"agent_id": str(agent_id), "result": result, "status": "success"})
            except asyncio.TimeoutError:
                results.append({"agent_id": str(agent_id), "result": None, "status": "timeout"})
            except Exception as e:
                results.append({"agent_id": str(agent_id), "result": None, "status": "error", "error": str(e)})

        return {"type": "parallel", "results": results}

    async def _execute_consensus(
        self,
        execution: WorkflowExecution,
        step: WorkflowStep,
    ) -> dict[str, Any]:
        """Execute agents and require consensus."""
        # First, execute in parallel
        parallel_result = await self._execute_parallel(execution, step)

        # Check consensus
        results = parallel_result["results"]
        successful_results = [r for r in results if r["status"] == "success"]

        consensus_rule = step.consensus_rule or "all_must_approve"

        if consensus_rule == "all_must_approve":
            consensus_reached = len(successful_results) == len(step.agent_ids)
            # Check all results agree
            if consensus_reached and len(successful_results) > 1:
                first_decision = successful_results[0]["result"].get("decision")
                consensus_reached = all(
                    r["result"].get("decision") == first_decision
                    for r in successful_results
                )
        elif consensus_rule == "majority":
            consensus_reached = len(successful_results) > len(step.agent_ids) / 2
        elif consensus_rule == "any":
            consensus_reached = len(successful_results) > 0
        else:
            consensus_reached = False

        return {
            "type": "consensus",
            "results": results,
            "consensus_reached": consensus_reached,
            "consensus_rule": consensus_rule,
        }

    async def _execute_conditional(
        self,
        execution: WorkflowExecution,
        step: WorkflowStep,
    ) -> dict[str, Any]:
        """Execute based on condition."""
        condition = step.condition or {}
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")

        # Get field value from shared state
        field_value = execution.shared_state.get(field)

        # Evaluate condition
        condition_met = False
        if operator == "equals":
            condition_met = field_value == value
        elif operator == "not_equals":
            condition_met = field_value != value
        elif operator == "contains":
            condition_met = value in str(field_value)
        elif operator == "greater_than":
            condition_met = field_value > value
        elif operator == "less_than":
            condition_met = field_value < value

        return {
            "type": "conditional",
            "condition": condition,
            "field_value": field_value,
            "condition_met": condition_met,
        }

    async def _execute_supervisor(
        self,
        execution: WorkflowExecution,
        step: WorkflowStep,
    ) -> dict[str, Any]:
        """Supervisor pattern - parent delegates to children."""
        # First agent is supervisor, rest are workers
        supervisor_id = step.agent_ids[0]
        worker_ids = step.agent_ids[1:]

        handler = self._step_handlers.get(step.handler)
        if not handler:
            raise OrchestrationError(f"Handler not found: {step.handler}")

        # Supervisor decides work distribution
        supervisor_context = {
            "agent_id": str(supervisor_id),
            "execution_id": str(execution.execution_id),
            "shared_state": execution.shared_state,
            "worker_ids": [str(w) for w in worker_ids],
            "role": "supervisor",
        }

        supervisor_result = await handler(supervisor_context, execution.shared_state)
        work_assignments = supervisor_result.get("assignments", {})

        # Execute worker tasks
        worker_results = []
        for worker_id in worker_ids:
            assignment = work_assignments.get(str(worker_id), {})
            worker_context = {
                "agent_id": str(worker_id),
                "execution_id": str(execution.execution_id),
                "shared_state": execution.shared_state,
                "assignment": assignment,
                "role": "worker",
            }

            try:
                result = await asyncio.wait_for(
                    handler(worker_context, execution.shared_state),
                    timeout=step.timeout_seconds,
                )
                worker_results.append({
                    "agent_id": str(worker_id),
                    "result": result,
                    "status": "success",
                })
            except Exception as e:
                worker_results.append({
                    "agent_id": str(worker_id),
                    "result": None,
                    "status": "error",
                    "error": str(e),
                })

        return {
            "type": "supervisor",
            "supervisor_id": str(supervisor_id),
            "supervisor_result": supervisor_result,
            "worker_results": worker_results,
        }

    def _find_step(self, workflow: Workflow, step_id: str) -> WorkflowStep | None:
        """Find a step in a workflow."""
        for step in workflow.steps:
            if step.step_id == step_id:
                return step
        return None

    def _determine_next_step(
        self,
        step: WorkflowStep,
        result: dict[str, Any],
        execution: WorkflowExecution,
    ) -> str | None:
        """Determine the next step based on current step result."""
        if not step.next_steps:
            return None

        # For conditional steps, use condition result
        if step.step_type == WorkflowStepType.CONDITIONAL:
            if result.get("condition_met"):
                return step.next_steps[0] if step.next_steps else None
            return step.next_steps[1] if len(step.next_steps) > 1 else None

        # For consensus, only proceed if consensus reached
        if step.step_type == WorkflowStepType.CONSENSUS:
            if not result.get("consensus_reached"):
                execution.status = WorkflowStatus.FAILED
                execution.error = "Consensus not reached"
                return None

        # Default: proceed to first next step
        return step.next_steps[0] if step.next_steps else None

    # =========================================================================
    # Shared State Management
    # =========================================================================

    async def set_shared_state(
        self,
        execution_id: UUID,
        key: str,
        value: Any,
        owner_agent_id: UUID,
        shared_with: list[UUID] | None = None,
    ) -> SharedState:
        """Set a shared state value."""
        if execution_id not in self._shared_state:
            self._shared_state[execution_id] = {}

        execution = self._executions.get(execution_id)
        if not execution:
            raise OrchestrationError(f"Execution not found: {execution_id}")

        state = SharedState(
            workflow_id=execution.workflow_id,
            tenant_id=execution.tenant_id,
            key=key,
            value=value,
            owner_agent_id=owner_agent_id,
            shared_with=shared_with or [],
        )

        self._shared_state[execution_id][key] = state
        execution.shared_state[key] = value

        logger.debug(
            "shared_state_set",
            execution_id=str(execution_id),
            key=key,
            owner=str(owner_agent_id),
        )

        return state

    async def get_shared_state(
        self,
        execution_id: UUID,
        key: str,
        requesting_agent_id: UUID,
    ) -> Any:
        """Get a shared state value."""
        states = self._shared_state.get(execution_id, {})
        state = states.get(key)

        if not state:
            return None

        # Check access
        if (
            state.owner_agent_id != requesting_agent_id
            and requesting_agent_id not in state.shared_with
            and state.shared_with  # Empty means shared with all
        ):
            raise AgentError(
                f"Access denied to shared state: {key}",
                details={"requesting_agent": str(requesting_agent_id)},
            )

        return state.value

    async def get_execution(self, execution_id: UUID) -> WorkflowExecution | None:
        """Get workflow execution by ID."""
        return self._executions.get(execution_id)

    async def list_executions(
        self,
        tenant_id: UUID,
        status: WorkflowStatus | None = None,
    ) -> list[WorkflowExecution]:
        """List workflow executions."""
        executions = [
            e for e in self._executions.values()
            if e.tenant_id == tenant_id
        ]

        if status:
            executions = [e for e in executions if e.status == status]

        return executions

    async def cancel_execution(
        self,
        execution_id: UUID,
        reason: str,
    ) -> WorkflowExecution:
        """Cancel a running workflow execution."""
        execution = self._executions.get(execution_id)
        if not execution:
            raise OrchestrationError(f"Execution not found: {execution_id}")

        if execution.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
            raise OrchestrationError(f"Cannot cancel: {execution.status}")

        execution.status = WorkflowStatus.CANCELLED
        execution.error = f"Cancelled: {reason}"
        execution.completed_at = datetime.utcnow()

        logger.info(
            "execution_cancelled",
            execution_id=str(execution_id),
            reason=reason,
        )

        return execution
