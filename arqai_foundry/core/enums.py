"""
Core enumerations used throughout ArqAI Foundry.
"""

from enum import Enum, auto


class ActionType(str, Enum):
    """Types of actions agents can perform."""

    # Resource lifecycle
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    TERMINATE = "terminate"
    STOP = "stop"
    START = "start"
    RESTART = "restart"
    SNAPSHOT = "snapshot"
    RESTORE = "restore"

    # Data operations
    EXPORT = "export"
    IMPORT = "import"
    TRANSFORM = "transform"
    VALIDATE = "validate"

    # Communication
    NOTIFY = "notify"
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"

    # Analysis
    ANALYZE = "analyze"
    RECOMMEND = "recommend"
    PREDICT = "predict"


class DataClassification(str, Enum):
    """Data sensitivity classifications."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PII = "pii"  # Personally Identifiable Information
    PHI = "phi"  # Protected Health Information
    PCI = "pci"  # Payment Card Industry data
    RESTRICTED = "restricted"


class Environment(str, Enum):
    """Deployment environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DR = "disaster_recovery"


class RiskTier(str, Enum):
    """Risk classification tiers."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyEffect(str, Enum):
    """Policy evaluation outcomes."""

    ALLOW = "allow"
    ALLOW_AUTO = "allow_auto"  # Automatic execution allowed
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    REQUIRE_MFA = "require_mfa"
    AUDIT_ONLY = "audit_only"  # Allow but flag for audit


class ExecutionStatus(str, Enum):
    """Execution pipeline states."""

    PENDING = "pending"
    COMPILING = "compiling"
    CHECKING = "checking"  # Policy check
    SCORING = "scoring"  # Risk scoring
    AWAITING_APPROVAL = "awaiting_approval"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    DENIED = "denied"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class AgentStatus(str, Enum):
    """Agent lifecycle states."""

    INITIALIZING = "initializing"
    ACTIVE = "active"
    PAUSED = "paused"
    SUSPENDED = "suspended"  # Policy violation
    TERMINATED = "terminated"
    ERROR = "error"


class ApprovalStatus(str, Enum):
    """Approval workflow states."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DELEGATED = "delegated"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class IntegrationStatus(str, Enum):
    """Integration connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"  # Partial functionality
    ERROR = "error"


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    MISTRAL = "mistral"
    AZURE_OPENAI = "azure_openai"
    AWS_BEDROCK = "aws_bedrock"
    CUSTOM = "custom"


class TemplateCategory(str, Enum):
    """Template vertical categories."""

    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    ENERGY = "energy"
    GOVERNMENT = "government"
    GENERAL = "general"


class MessagePriority(str, Enum):
    """Agent message priorities."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
