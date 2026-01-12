"""
Global configuration for ArqAI Foundry.

All configuration is loaded from environment variables with sensible defaults.
Secrets are loaded from HashiCorp Vault in production.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="DB_")

    host: str = "localhost"
    port: int = 5432
    name: str = "arqai_foundry"
    user: str = "arqai"
    password: SecretStr = SecretStr("arqai_dev_password")
    pool_size: int = 20
    max_overflow: int = 10

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.name}"


class RedisSettings(BaseSettings):
    """Redis configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: SecretStr | None = None

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class VaultSettings(BaseSettings):
    """HashiCorp Vault configuration."""

    model_config = SettingsConfigDict(env_prefix="VAULT_")

    enabled: bool = True
    url: str = "http://localhost:8200"
    token: SecretStr | None = None
    namespace: str | None = None
    mount_point: str = "secret"
    # For Kubernetes auth
    k8s_role: str | None = None
    k8s_mount_point: str = "kubernetes"


class IdentitySettings(BaseSettings):
    """Identity and key management configuration."""

    model_config = SettingsConfigDict(env_prefix="IDENTITY_")

    # Key rotation schedules (in days)
    agent_key_rotation_days: int = 90
    token_signing_key_rotation_days: int = 7
    evidence_signing_key_rotation_days: int = 365

    # Token settings
    capability_token_max_ttl_seconds: int = 300  # 5 minutes
    capability_token_default_ttl_seconds: int = 60  # 1 minute

    # Certificate settings
    root_ca_validity_years: int = 10
    intermediate_ca_validity_years: int = 5
    agent_cert_validity_days: int = 90


class PolicySettings(BaseSettings):
    """Policy engine configuration."""

    model_config = SettingsConfigDict(env_prefix="POLICY_")

    # Performance
    evaluation_timeout_ms: int = 100
    cache_ttl_seconds: int = 3600  # 1 hour

    # Defaults
    default_risk_threshold_low: int = 30
    default_risk_threshold_medium: int = 60
    default_risk_threshold_high: int = 80


class EvidenceSettings(BaseSettings):
    """Evidence vault configuration."""

    model_config = SettingsConfigDict(env_prefix="EVIDENCE_")

    # Retention
    retention_years: int = 7

    # Performance
    write_batch_size: int = 100
    verification_timeout_ms: int = 50

    # Public verification
    public_verification_enabled: bool = True
    public_rate_limit_per_minute: int = 100


class LLMSettings(BaseSettings):
    """LLM configuration."""

    model_config = SettingsConfigDict(env_prefix="LLM_")

    # Default provider
    default_provider: str = "anthropic"
    default_model: str = "claude-sonnet-4-20250514"

    # Rate limiting
    rate_limit_requests_per_minute: int = 60
    rate_limit_tokens_per_minute: int = 100000

    # Cost tracking
    cost_tracking_enabled: bool = True
    budget_alert_threshold_percent: int = 80

    # Timeouts
    request_timeout_seconds: int = 60
    stream_timeout_seconds: int = 120


class IntegrationSettings(BaseSettings):
    """Integration configuration."""

    model_config = SettingsConfigDict(env_prefix="INTEGRATION_")

    # Health checks
    health_check_interval_seconds: int = 60

    # Retry settings
    max_retries: int = 3
    retry_backoff_base_seconds: float = 1.0
    retry_backoff_max_seconds: float = 60.0

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_seconds: int = 30


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="ARQAI_",
        env_nested_delimiter="__",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    # Security
    secret_key: SecretStr = SecretStr("dev-secret-key-change-in-production")
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    vault: VaultSettings = Field(default_factory=VaultSettings)
    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    policy: PolicySettings = Field(default_factory=PolicySettings)
    evidence: EvidenceSettings = Field(default_factory=EvidenceSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    integration: IntegrationSettings = Field(default_factory=IntegrationSettings)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
