"""
HashiCorp Vault client for secure secret and key management.

Provides:
- Secret storage and retrieval
- PKI operations for certificate management
- Transit encryption for data protection
- Key rotation automation
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import hvac
from hvac.exceptions import VaultError
import structlog

from arqai_foundry.config import get_settings
from arqai_foundry.core.exceptions import (
    AuthenticationError,
    CertificateError,
)

logger = structlog.get_logger(__name__)


class VaultClient:
    """Async wrapper for HashiCorp Vault operations."""

    def __init__(self):
        self.settings = get_settings().vault
        self._client: hvac.Client | None = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> hvac.Client:
        """Get or create authenticated Vault client."""
        if self._client is not None and self._client.is_authenticated():
            return self._client

        async with self._lock:
            # Double-check after acquiring lock
            if self._client is not None and self._client.is_authenticated():
                return self._client

            self._client = hvac.Client(
                url=self.settings.url,
                namespace=self.settings.namespace,
            )

            # Authenticate based on available credentials
            if self.settings.token:
                self._client.token = self.settings.token.get_secret_value()
            elif self.settings.k8s_role:
                # Kubernetes auth for production
                await self._kubernetes_auth()
            else:
                raise AuthenticationError(
                    "No Vault authentication method configured",
                    details={"url": self.settings.url},
                )

            if not self._client.is_authenticated():
                raise AuthenticationError(
                    "Failed to authenticate with Vault",
                    details={"url": self.settings.url},
                )

            logger.info("vault_authenticated", url=self.settings.url)
            return self._client

    async def _kubernetes_auth(self) -> None:
        """Authenticate using Kubernetes service account."""
        try:
            with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
                jwt = f.read()

            self._client.auth.kubernetes.login(
                role=self.settings.k8s_role,
                jwt=jwt,
                mount_point=self.settings.k8s_mount_point,
            )
        except Exception as e:
            raise AuthenticationError(
                f"Kubernetes auth failed: {e}",
                details={"role": self.settings.k8s_role},
            )

    # =========================================================================
    # Secret Operations
    # =========================================================================

    async def read_secret(self, path: str) -> dict[str, Any]:
        """Read a secret from Vault KV store."""
        client = await self._get_client()
        try:
            response = client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.settings.mount_point,
            )
            return response["data"]["data"]
        except VaultError as e:
            logger.error("vault_read_secret_failed", path=path, error=str(e))
            raise

    async def write_secret(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        """Write a secret to Vault KV store."""
        client = await self._get_client()
        try:
            response = client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data,
                mount_point=self.settings.mount_point,
            )
            logger.info("vault_secret_written", path=path)
            return response
        except VaultError as e:
            logger.error("vault_write_secret_failed", path=path, error=str(e))
            raise

    async def delete_secret(self, path: str) -> None:
        """Delete a secret from Vault KV store."""
        client = await self._get_client()
        try:
            client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=self.settings.mount_point,
            )
            logger.info("vault_secret_deleted", path=path)
        except VaultError as e:
            logger.error("vault_delete_secret_failed", path=path, error=str(e))
            raise

    # =========================================================================
    # PKI Operations
    # =========================================================================

    async def setup_pki_root(
        self,
        mount_point: str = "pki",
        common_name: str = "ArqAI Root CA",
        ttl: str = "87600h",  # 10 years
    ) -> dict[str, Any]:
        """Set up PKI root CA (one-time operation)."""
        client = await self._get_client()
        try:
            # Enable PKI engine if not already enabled
            try:
                client.sys.enable_secrets_engine(
                    backend_type="pki",
                    path=mount_point,
                    config={"max_lease_ttl": ttl},
                )
            except VaultError:
                pass  # Already enabled

            # Generate root certificate
            response = client.secrets.pki.generate_root(
                type="internal",
                common_name=common_name,
                ttl=ttl,
                mount_point=mount_point,
            )

            logger.info("pki_root_ca_created", mount_point=mount_point)
            return response["data"]
        except VaultError as e:
            logger.error("pki_root_setup_failed", error=str(e))
            raise CertificateError(f"Failed to set up PKI root: {e}")

    async def setup_pki_intermediate(
        self,
        tenant_id: str,
        root_mount: str = "pki",
        ttl: str = "43800h",  # 5 years
    ) -> dict[str, Any]:
        """Set up intermediate CA for a tenant."""
        client = await self._get_client()
        intermediate_mount = f"pki-tenant-{tenant_id}"

        try:
            # Enable intermediate PKI
            try:
                client.sys.enable_secrets_engine(
                    backend_type="pki",
                    path=intermediate_mount,
                    config={"max_lease_ttl": ttl},
                )
            except VaultError:
                pass  # Already enabled

            # Generate CSR
            csr_response = client.secrets.pki.generate_intermediate(
                type="internal",
                common_name=f"ArqAI Tenant {tenant_id} Intermediate CA",
                mount_point=intermediate_mount,
            )
            csr = csr_response["data"]["csr"]

            # Sign with root CA
            sign_response = client.secrets.pki.sign_intermediate(
                csr=csr,
                common_name=f"ArqAI Tenant {tenant_id} Intermediate CA",
                ttl=ttl,
                mount_point=root_mount,
            )
            certificate = sign_response["data"]["certificate"]

            # Set signed certificate
            client.secrets.pki.set_signed_intermediate(
                certificate=certificate,
                mount_point=intermediate_mount,
            )

            logger.info(
                "pki_intermediate_ca_created",
                tenant_id=tenant_id,
                mount_point=intermediate_mount,
            )

            return {
                "mount_point": intermediate_mount,
                "certificate": certificate,
            }
        except VaultError as e:
            logger.error(
                "pki_intermediate_setup_failed",
                tenant_id=tenant_id,
                error=str(e),
            )
            raise CertificateError(f"Failed to set up intermediate CA: {e}")

    async def issue_certificate(
        self,
        tenant_id: str,
        common_name: str,
        ttl: str = "2160h",  # 90 days
        alt_names: list[str] | None = None,
        ip_sans: list[str] | None = None,
        extra_extensions: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Issue a certificate from tenant's intermediate CA."""
        client = await self._get_client()
        intermediate_mount = f"pki-tenant-{tenant_id}"

        try:
            # Create role if not exists
            role_name = "agent-cert"
            try:
                client.secrets.pki.create_or_update_role(
                    name=role_name,
                    mount_point=intermediate_mount,
                    allowed_domains=["arqai.local"],
                    allow_subdomains=True,
                    allow_any_name=True,
                    max_ttl=ttl,
                    generate_lease=True,
                )
            except VaultError:
                pass  # Role exists

            # Issue certificate
            response = client.secrets.pki.generate_certificate(
                name=role_name,
                common_name=common_name,
                ttl=ttl,
                mount_point=intermediate_mount,
            )

            cert_data = response["data"]
            logger.info(
                "certificate_issued",
                tenant_id=tenant_id,
                common_name=common_name,
                serial=cert_data.get("serial_number"),
            )

            return {
                "certificate": cert_data["certificate"],
                "private_key": cert_data["private_key"],
                "ca_chain": cert_data.get("ca_chain", []),
                "serial_number": cert_data["serial_number"],
                "expiration": cert_data["expiration"],
            }
        except VaultError as e:
            logger.error(
                "certificate_issuance_failed",
                tenant_id=tenant_id,
                common_name=common_name,
                error=str(e),
            )
            raise CertificateError(f"Failed to issue certificate: {e}")

    async def revoke_certificate(
        self,
        tenant_id: str,
        serial_number: str,
    ) -> None:
        """Revoke a certificate."""
        client = await self._get_client()
        intermediate_mount = f"pki-tenant-{tenant_id}"

        try:
            client.secrets.pki.revoke_certificate(
                serial_number=serial_number,
                mount_point=intermediate_mount,
            )
            logger.info(
                "certificate_revoked",
                tenant_id=tenant_id,
                serial_number=serial_number,
            )
        except VaultError as e:
            logger.error(
                "certificate_revocation_failed",
                tenant_id=tenant_id,
                serial_number=serial_number,
                error=str(e),
            )
            raise CertificateError(f"Failed to revoke certificate: {e}")

    # =========================================================================
    # Transit Encryption
    # =========================================================================

    async def setup_transit_key(
        self,
        key_name: str,
        key_type: str = "aes256-gcm96",
        mount_point: str = "transit",
    ) -> None:
        """Create a transit encryption key."""
        client = await self._get_client()
        try:
            # Enable transit engine if not already enabled
            try:
                client.sys.enable_secrets_engine(
                    backend_type="transit",
                    path=mount_point,
                )
            except VaultError:
                pass  # Already enabled

            client.secrets.transit.create_key(
                name=key_name,
                key_type=key_type,
                mount_point=mount_point,
            )
            logger.info("transit_key_created", key_name=key_name)
        except VaultError as e:
            logger.error("transit_key_creation_failed", key_name=key_name, error=str(e))
            raise

    async def encrypt(
        self,
        key_name: str,
        plaintext: str,
        mount_point: str = "transit",
    ) -> str:
        """Encrypt data using transit key."""
        client = await self._get_client()
        try:
            import base64

            encoded = base64.b64encode(plaintext.encode()).decode()
            response = client.secrets.transit.encrypt_data(
                name=key_name,
                plaintext=encoded,
                mount_point=mount_point,
            )
            return response["data"]["ciphertext"]
        except VaultError as e:
            logger.error("encryption_failed", key_name=key_name, error=str(e))
            raise

    async def decrypt(
        self,
        key_name: str,
        ciphertext: str,
        mount_point: str = "transit",
    ) -> str:
        """Decrypt data using transit key."""
        client = await self._get_client()
        try:
            import base64

            response = client.secrets.transit.decrypt_data(
                name=key_name,
                ciphertext=ciphertext,
                mount_point=mount_point,
            )
            decoded = base64.b64decode(response["data"]["plaintext"]).decode()
            return decoded
        except VaultError as e:
            logger.error("decryption_failed", key_name=key_name, error=str(e))
            raise

    async def sign_data(
        self,
        key_name: str,
        data: str,
        hash_algorithm: str = "sha2-256",
        mount_point: str = "transit",
    ) -> str:
        """Sign data using transit key."""
        client = await self._get_client()
        try:
            import base64
            import hashlib

            # Hash the data
            data_hash = hashlib.sha256(data.encode()).digest()
            encoded_hash = base64.b64encode(data_hash).decode()

            response = client.secrets.transit.sign_data(
                name=key_name,
                hash_input=encoded_hash,
                hash_algorithm=hash_algorithm,
                prehashed=True,
                mount_point=mount_point,
            )
            return response["data"]["signature"]
        except VaultError as e:
            logger.error("signing_failed", key_name=key_name, error=str(e))
            raise

    async def verify_signature(
        self,
        key_name: str,
        data: str,
        signature: str,
        hash_algorithm: str = "sha2-256",
        mount_point: str = "transit",
    ) -> bool:
        """Verify a signature using transit key."""
        client = await self._get_client()
        try:
            import base64
            import hashlib

            data_hash = hashlib.sha256(data.encode()).digest()
            encoded_hash = base64.b64encode(data_hash).decode()

            response = client.secrets.transit.verify_signed_data(
                name=key_name,
                hash_input=encoded_hash,
                signature=signature,
                hash_algorithm=hash_algorithm,
                prehashed=True,
                mount_point=mount_point,
            )
            return response["data"]["valid"]
        except VaultError as e:
            logger.error("verification_failed", key_name=key_name, error=str(e))
            return False

    async def rotate_key(
        self,
        key_name: str,
        mount_point: str = "transit",
    ) -> None:
        """Rotate a transit key."""
        client = await self._get_client()
        try:
            client.secrets.transit.rotate_key(
                name=key_name,
                mount_point=mount_point,
            )
            logger.info("transit_key_rotated", key_name=key_name)
        except VaultError as e:
            logger.error("key_rotation_failed", key_name=key_name, error=str(e))
            raise


# Singleton instance
_vault_client: VaultClient | None = None


def get_vault_client() -> VaultClient:
    """Get singleton Vault client instance."""
    global _vault_client
    if _vault_client is None:
        _vault_client = VaultClient()
    return _vault_client
