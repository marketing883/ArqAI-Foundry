"""
Identity & Key Management Service

Provides cryptographic trust foundation with:
- HSM-backed identities via HashiCorp Vault
- Hierarchical key management (Root CA → Tenant CA → Agent certs)
- Automated key rotation
- Single-use capability tokens
"""

from services.identity.key_management import KeyManagementService
from services.identity.agent_identity import AgentIdentityService
from services.identity.capability_tokens import CapabilityTokenService
from services.identity.trust_anchor import TrustAnchorRegistry

__all__ = [
    "KeyManagementService",
    "AgentIdentityService",
    "CapabilityTokenService",
    "TrustAnchorRegistry",
]
