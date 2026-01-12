"""
Core domain models for ArqAI Foundry.

These models represent the fundamental concepts in the system:
- Agent identities and capability tokens
- Intents and compiled IR
- Policies and risk assessments
- Evidence packets
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field

from arqai_foundry.core.enums import (
    ActionType,
    ApprovalStatus,
    DataClassification,
    Environment,
    ExecutionStatus,
    PolicyEffect,
    RiskTier,
)


# =============================================================================
# Identity Models
# =============================================================================


class AgentIdentity(BaseModel):
    """Cryptographic identity for an agent instance."""

    agent_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    template_id: str
    deployment_environment: Environment

    # Certificate info
    certificate_fingerprint: str
    public_key: str
    issued_at: datetime
    expires_at: datetime
    issuer: str  # Tenant Intermediate CA

    # Status
    is_active: bool = True
    suspended_at: datetime | None = None
    suspension_reason: str | None = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity_at: datetime | None = None
    rotation_count: int = 0

    @computed_field
    @property
    def is_valid(self) -> bool:
        """Check if identity is currently valid."""
        now = datetime.utcnow()
        return (
            self.is_active
            and self.issued_at <= now <= self.expires_at
            and self.suspended_at is None
        )


class CapabilityToken(BaseModel):
    """Single-use, time-bound, scoped authorization token."""

    token_id: UUID = Field(default_factory=uuid4)
    agent_identity: str  # Certificate fingerprint

    # Scope
    resource_id: str
    action: ActionType
    constraints: dict[str, Any] = Field(default_factory=dict)

    # Timing
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    one_time_nonce: str  # Ensures single use

    # Signature
    signature: str

    # Usage tracking
    used_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None

    @computed_field
    @property
    def is_valid(self) -> bool:
        """Check if token is currently valid."""
        now = datetime.utcnow()
        return (
            self.used_at is None
            and self.revoked_at is None
            and self.issued_at <= now <= self.expires_at
        )

    @computed_field
    @property
    def ttl_seconds(self) -> int:
        """Remaining time-to-live in seconds."""
        now = datetime.utcnow()
        if now >= self.expires_at:
            return 0
        return int((self.expires_at - now).total_seconds())


# =============================================================================
# Intent & IR Models
# =============================================================================


class IntentTarget(BaseModel):
    """Target resource for an intent."""

    resource_type: str
    resource_id: str
    provider: str  # e.g., "aws", "azure", "jira"
    region: str | None = None
    account_id: str | None = None


class IntentJustification(BaseModel):
    """Justification for an intent (for audit trail)."""

    project_id: str | None = None
    project_status: str | None = None
    idle_days: int | None = None
    reason: str
    additional_context: dict[str, Any] = Field(default_factory=dict)


class Intent(BaseModel):
    """Structured intent from user or agent."""

    intent_id: UUID = Field(default_factory=uuid4)
    intent_type: str  # e.g., "cost_optimization.terminate"
    version: str  # Schema version

    action: ActionType
    target: IntentTarget
    environment: Environment
    justification: IntentJustification

    # Source
    source_agent_id: UUID | None = None
    source_user_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Natural language (optional, for audit)
    natural_language_input: str | None = None


class IROperation(BaseModel):
    """Compiled intermediate representation operation."""

    op_id: UUID = Field(default_factory=uuid4)
    type: str  # e.g., "cloud.ec2.terminate"
    target: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    # Compliance annotations
    data_classification: DataClassification
    environment: Environment
    jurisdiction: list[str] = Field(default_factory=list)

    # Impact analysis
    estimated_cost_impact: dict[str, float] | None = None
    affected_resources: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)

    # Rollback info
    rollback_supported: bool = False
    rollback_operations: list[dict[str, Any]] = Field(default_factory=list)


class CompiledIR(BaseModel):
    """Complete compiled intermediate representation."""

    ir_id: UUID = Field(default_factory=uuid4)
    ir_version: str = "1.0.0"

    # Source intent
    intent_id: UUID
    intent_type: str

    # Operations
    operations: list[IROperation]

    # Policy requirements (determined during compilation)
    policy_requirements: dict[str, Any] = Field(default_factory=dict)

    # Compilation metadata
    compiled_at: datetime = Field(default_factory=datetime.utcnow)
    policy_version: str
    schema_version: str
    compiler_version: str = "1.0.0"


# =============================================================================
# Policy & Risk Models
# =============================================================================


class PolicyRule(BaseModel):
    """A single policy rule."""

    rule_id: str
    name: str
    priority: int  # Higher = evaluated first
    condition: dict[str, Any]
    effect: PolicyEffect
    evidence_required: bool = True

    # For require_approval effect
    approvers: list[dict[str, str]] = Field(default_factory=list)
    timeout_hours: int = 24
    delegation_allowed: bool = False


class Policy(BaseModel):
    """Complete policy definition."""

    policy_id: str
    version: str
    tenant_id: UUID
    name: str
    description: str | None = None

    # Scope
    jurisdiction: list[str] = Field(default_factory=list)
    environments: list[Environment] = Field(default_factory=list)

    # Rules
    rules: list[PolicyRule]

    # Risk scoring configuration
    risk_scoring: dict[str, Any] = Field(default_factory=dict)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str
    is_active: bool = True


class PolicyEvaluationResult(BaseModel):
    """Result of policy evaluation."""

    evaluation_id: UUID = Field(default_factory=uuid4)
    policy_id: str
    policy_version: str
    policy_hash: str

    # Result
    allowed: bool
    effect: PolicyEffect
    matched_rules: list[str]

    # Risk assessment
    risk_score: int
    risk_tier: RiskTier

    # Requirements
    required_approvals: list[dict[str, str]] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)

    # Performance
    evaluation_time_ms: float

    # Timestamp
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class RiskFactor(BaseModel):
    """Individual risk factor contribution."""

    name: str
    weight: float
    raw_value: Any
    score: int
    explanation: str


class RiskAssessment(BaseModel):
    """Complete risk assessment."""

    assessment_id: UUID = Field(default_factory=uuid4)

    # Scores
    risk_score: int  # 0-100
    risk_tier: RiskTier

    # Factor breakdown
    factors: list[RiskFactor]
    reasoning: list[str]

    # Timestamp
    assessed_at: datetime = Field(default_factory=datetime.utcnow)
    assessment_time_ms: float


# =============================================================================
# Evidence Models
# =============================================================================


class EvidencePacket(BaseModel):
    """Immutable, signed audit evidence packet."""

    # Public fields (always disclosed)
    evidence_id: UUID = Field(default_factory=uuid4)
    schema_version: str = "2.0"
    evidence_hash: str
    signature: str
    verification_url: str | None = None

    # Protected fields (require auth)
    tenant_id: UUID
    agent_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Evidence content
    request: dict[str, Any]  # Original intent
    compliance_ir: dict[str, Any]  # Compiled IR
    policy_validation: dict[str, Any]  # Policy evaluation result
    risk_assessment: dict[str, Any]  # Risk scoring result
    capability_token: dict[str, Any]  # Token used (redacted signature)

    # Execution details
    execution: dict[str, Any]  # Pre/post state, action trace

    # Financial impact
    financial_impact: dict[str, float] | None = None

    # Chain integrity
    previous_hash: str | None = None
    block_number: int

    @computed_field
    @property
    def public_view(self) -> dict[str, Any]:
        """Return public-only fields for verification."""
        return {
            "evidence_id": str(self.evidence_id),
            "schema_version": self.schema_version,
            "evidence_hash": self.evidence_hash,
            "timestamp_hour": self.timestamp.replace(
                minute=0, second=0, microsecond=0
            ).isoformat(),
        }


# =============================================================================
# Orchestration Models
# =============================================================================


class ExecutionContext(BaseModel):
    """Context for an execution pipeline."""

    execution_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID
    agent_id: UUID

    # Pipeline state
    status: ExecutionStatus = ExecutionStatus.PENDING
    current_stage: str = "pending"

    # Artifacts
    intent: Intent | None = None
    compiled_ir: CompiledIR | None = None
    policy_result: PolicyEvaluationResult | None = None
    risk_assessment: RiskAssessment | None = None
    capability_token: CapabilityToken | None = None
    evidence_id: UUID | None = None

    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    # Error handling
    error: str | None = None
    error_details: dict[str, Any] | None = None


class ApprovalRequest(BaseModel):
    """Request for human approval."""

    approval_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID

    # Summary
    action_summary: str
    risk_score: int
    risk_tier: RiskTier

    # Requirements
    required_approvers: list[dict[str, str]]
    timeout_hours: int = 24
    delegation_allowed: bool = False

    # Evidence preview
    resources_affected: list[str]
    estimated_savings: str | None = None

    # Status
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: str | None = None
    rejected_by: str | None = None
    rejection_reason: str | None = None

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    resolved_at: datetime | None = None


# =============================================================================
# Agent Communication Models
# =============================================================================


class AgentMessage(BaseModel):
    """Message for agent-to-agent communication."""

    message_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID  # Links related messages

    # Routing
    from_agent_id: UUID
    to_agent_id: UUID | None = None  # None = broadcast
    topic: str  # Message topic/channel

    # Content
    message_type: str  # e.g., "task_request", "task_complete", "data_share"
    payload: dict[str, Any]
    priority: str = "normal"

    # Timing
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    acknowledged_at: datetime | None = None


class SharedState(BaseModel):
    """Shared state between agents."""

    state_id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    tenant_id: UUID

    # State data
    key: str
    value: Any
    version: int = 1

    # Access control
    owner_agent_id: UUID
    shared_with: list[UUID] = Field(default_factory=list)

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
