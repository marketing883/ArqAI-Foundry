"""
Custom exceptions for ArqAI Foundry.

All exceptions inherit from ArqAIError for consistent handling.
"""

from typing import Any


class ArqAIError(Exception):
    """Base exception for all ArqAI Foundry errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# Authentication & Authorization Errors


class AuthenticationError(ArqAIError):
    """Authentication failed."""

    pass


class AuthorizationError(ArqAIError):
    """Authorization denied."""

    pass


class TokenError(ArqAIError):
    """Token-related errors."""

    pass


class TokenExpiredError(TokenError):
    """Token has expired."""

    pass


class TokenRevokedError(TokenError):
    """Token has been revoked."""

    pass


class TokenAlreadyUsedError(TokenError):
    """Single-use token has already been used."""

    pass


class TokenScopeMismatchError(TokenError):
    """Token scope doesn't match requested action."""

    pass


# Identity Errors


class IdentityError(ArqAIError):
    """Identity-related errors."""

    pass


class IdentityNotFoundError(IdentityError):
    """Agent identity not found."""

    pass


class IdentitySuspendedError(IdentityError):
    """Agent identity has been suspended."""

    pass


class CertificateError(IdentityError):
    """Certificate-related errors."""

    pass


# Policy Errors


class PolicyError(ArqAIError):
    """Policy-related errors."""

    pass


class PolicyViolationError(PolicyError):
    """Action violates policy."""

    def __init__(
        self,
        message: str,
        policy_id: str,
        rule_id: str,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details=details)
        self.policy_id = policy_id
        self.rule_id = rule_id
        self.details["policy_id"] = policy_id
        self.details["rule_id"] = rule_id


class PolicyNotFoundError(PolicyError):
    """Policy not found."""

    pass


class PolicyEvaluationError(PolicyError):
    """Policy evaluation failed."""

    pass


# Compilation Errors


class CompilationError(ArqAIError):
    """Intent compilation failed."""

    pass


class SchemaValidationError(CompilationError):
    """Intent doesn't match schema."""

    def __init__(
        self,
        message: str,
        schema_errors: list[dict[str, Any]],
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details=details)
        self.schema_errors = schema_errors
        self.details["schema_errors"] = schema_errors


class AmbiguousIntentError(CompilationError):
    """Intent is ambiguous and cannot be compiled."""

    pass


# Evidence Errors


class EvidenceError(ArqAIError):
    """Evidence-related errors."""

    pass


class EvidenceNotFoundError(EvidenceError):
    """Evidence packet not found."""

    pass


class EvidenceVerificationError(EvidenceError):
    """Evidence verification failed."""

    pass


class EvidenceChainError(EvidenceError):
    """Evidence chain integrity compromised."""

    pass


# Risk Scoring Errors


class RiskScoringError(ArqAIError):
    """Risk scoring failed."""

    pass


class RiskThresholdExceededError(RiskScoringError):
    """Risk score exceeds allowed threshold."""

    def __init__(
        self,
        message: str,
        risk_score: int,
        threshold: int,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details=details)
        self.risk_score = risk_score
        self.threshold = threshold
        self.details["risk_score"] = risk_score
        self.details["threshold"] = threshold


# Orchestration Errors


class OrchestrationError(ArqAIError):
    """Orchestration pipeline errors."""

    pass


class ExecutionError(OrchestrationError):
    """Action execution failed."""

    pass


class RollbackError(OrchestrationError):
    """Rollback failed."""

    pass


class ApprovalTimeoutError(OrchestrationError):
    """Approval request timed out."""

    pass


# Integration Errors


class IntegrationError(ArqAIError):
    """Integration-related errors."""

    pass


class ConnectionError(IntegrationError):
    """Failed to connect to external service."""

    pass


class RateLimitError(IntegrationError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str,
        retry_after_seconds: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details=details)
        self.retry_after_seconds = retry_after_seconds
        if retry_after_seconds:
            self.details["retry_after_seconds"] = retry_after_seconds


class PermissionDeniedError(IntegrationError):
    """Permission denied by external service."""

    pass


# LLM Errors


class LLMError(ArqAIError):
    """LLM-related errors."""

    pass


class LLMProviderError(LLMError):
    """LLM provider returned an error."""

    pass


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    pass


class LLMBudgetExceededError(LLMError):
    """LLM usage budget exceeded."""

    pass


# Template Errors


class TemplateError(ArqAIError):
    """Template-related errors."""

    pass


class TemplateNotFoundError(TemplateError):
    """Template not found."""

    pass


class TemplateValidationError(TemplateError):
    """Template configuration invalid."""

    pass


# Agent Errors


class AgentError(ArqAIError):
    """Agent-related errors."""

    pass


class AgentNotFoundError(AgentError):
    """Agent not found."""

    pass


class AgentCommunicationError(AgentError):
    """Agent-to-agent communication failed."""

    pass
