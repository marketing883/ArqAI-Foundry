"""
Multi-Agent Orchestration Engine

Provides:
- Orchestration Pipeline (compile → check → score → authorize → execute → evidence)
- Multi-Agent Coordination (message bus, shared state)
- Approval Workflow Service
- Action Executor
"""

from services.orchestration.pipeline import OrchestrationPipeline
from services.orchestration.executor import ActionExecutor
from services.orchestration.approval import ApprovalWorkflowService
from services.orchestration.message_bus.bus import MessageBus
from services.orchestration.coordinator.coordinator import AgentCoordinator

__all__ = [
    "OrchestrationPipeline",
    "ActionExecutor",
    "ApprovalWorkflowService",
    "MessageBus",
    "AgentCoordinator",
]
