"""
Core domain models and abstractions for ArqAI Foundry.
"""

from arqai_foundry.core.models import (
    AgentIdentity,
    CapabilityToken,
    EvidencePacket,
    Intent,
    IROperation,
    PolicyEvaluationResult,
    RiskAssessment,
)
from arqai_foundry.core.enums import (
    ActionType,
    DataClassification,
    Environment,
    RiskTier,
    PolicyEffect,
    ExecutionStatus,
)
from arqai_foundry.core.exceptions import (
    ArqAIError,
    AuthenticationError,
    AuthorizationError,
    PolicyViolationError,
    CompilationError,
    EvidenceError,
    IntegrationError,
)

__all__ = [
    # Models
    "AgentIdentity",
    "CapabilityToken",
    "EvidencePacket",
    "Intent",
    "IROperation",
    "PolicyEvaluationResult",
    "RiskAssessment",
    # Enums
    "ActionType",
    "DataClassification",
    "Environment",
    "RiskTier",
    "PolicyEffect",
    "ExecutionStatus",
    # Exceptions
    "ArqAIError",
    "AuthenticationError",
    "AuthorizationError",
    "PolicyViolationError",
    "CompilationError",
    "EvidenceError",
    "IntegrationError",
]
