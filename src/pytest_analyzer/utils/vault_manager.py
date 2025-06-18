import logging
import time
from functools import wraps
from typing import Any, Dict, Optional, Tuple

import hvac
from hvac.exceptions import VaultError as HVACError

from .config_types import VaultSettings

logger = logging.getLogger(__name__)


class VaultError(Exception):
    """Custom exception for Vault-related errors."""

    pass


def _log_access(func):
    """Decorator to log secret access for auditing."""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        path = kwargs.get("path") or (args[0] if args else "unknown")
        key = kwargs.get("key") or (args[1] if len(args) > 1 else "unknown")
        secret_ref = f"{self.settings.mount_point}/{path}#{key}"
        start_time = time.time()
        try:
            result = func(self, *args, **kwargs)
            duration = (time.time() - start_time) * 1000
            # Log access without sensitive data
            logger.info(
                f"Successfully accessed Vault secret '{secret_ref}'. Duration: {duration:.2f}ms"
            )
            return result
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            # Log error without exposing sensitive data - only log error type and reference
            error_type = type(e).__name__
            logger.error(
                f"Failed to access Vault secret '{secret_ref}'. Duration: {duration:.2f}ms. Error type: {error_type}",
                exc_info=False,  # Disable stack trace to avoid potential sensitive data exposure
            )
            raise

    return wrapper


class VaultSecretManager:
    """
    Manages interaction with HashiCorp Vault for secure secret retrieval.

    Features:
    - Connects to Vault using token or AppRole authentication.
    - Retrieves secrets from a specified KV secrets engine mount point.
    - Caches secrets in memory with a configurable TTL to reduce requests.
    - Provides auditing logs for all secret access attempts.
    - Handles Vault-specific errors and provides clear exceptions.
    """

    def __init__(self, settings: VaultSettings):
        if not settings.enabled:
            raise VaultError("VaultSecretManager cannot be initialized while disabled.")
        self.settings = settings
        self._client: Optional[hvac.Client] = None
        self._cache: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expiry_time)

    @property
    def client(self) -> hvac.Client:
        """Lazy-initialized HVAC client."""
        if self._client is None or not self._client.is_authenticated():
            self._connect()
        if self._client is None:
            # Should not happen if _connect is successful
            raise VaultError("Failed to establish an authenticated Vault client.")
        return self._client

    def _connect(self) -> None:
        """Establish a connection to the Vault server and authenticate."""
        logger.info(f"Connecting to Vault at {self.settings.url}...")
        try:
            client = hvac.Client(
                url=str(self.settings.url), timeout=self.settings.timeout
            )

            if self.settings.auth_method == "token":
                client.token = self.settings.token
            elif self.settings.auth_method == "approle":
                if not self.settings.role_id or not self.settings.secret_id:
                    raise VaultError("AppRole RoleID and SecretID are required.")
                hvac.api.auth_methods.AppRole(client.adapter).login(
                    role_id=self.settings.role_id,
                    secret_id=self.settings.secret_id,
                    use_token=True,
                    unwrap_cubbyhole=self.settings.unwrap_cubbyhole,
                )
            else:
                raise VaultError(
                    f"Unsupported Vault auth method: {self.settings.auth_method}"
                )

            if not client.is_authenticated():
                raise VaultError("Vault authentication failed.")

            self._client = client
            logger.info("Successfully authenticated with Vault.")
        except HVACError as e:
            logger.error(f"Vault connection or authentication error: {e}")
            raise VaultError(
                f"Failed to connect or authenticate with Vault: {e}"
            ) from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during Vault connection: {e}")
            raise VaultError(f"An unexpected error occurred: {e}") from e

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if a cached item is still valid."""
        if self.settings.cache_ttl <= 0:
            return False
        if cache_key not in self._cache:
            return False
        _, expiry_time = self._cache[cache_key]
        return time.time() < expiry_time

    @_log_access
    def get_secret(self, path: str, key: str, version: Optional[int] = None) -> Any:
        """
        Retrieve a secret's value from Vault, using a cache if available.

        Args:
            path: The path to the secret in the KV engine.
            key: The key of the value within the secret's data.
            version: The specific version of the secret to retrieve (for KVv2).

        Returns:
            The value of the requested secret key.

        Raises:
            VaultError: If the secret, key, or version cannot be found, or if there's a communication error.
        """
        cache_key = f"{path}#{key}"
        if version:
            cache_key += f"@{version}"

        if self._is_cache_valid(cache_key):
            logger.debug(f"Returning cached value for secret '{cache_key}'.")
            return self._cache[cache_key][0]

        logger.debug(f"Fetching secret '{cache_key}' from Vault.")
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.settings.mount_point,
                version=version,
            )
            secret_data = response.get("data", {}).get("data", {})

            if key not in secret_data:
                raise VaultError(f"Key '{key}' not found in secret at path '{path}'.")

            value = secret_data[key]

            # Update cache
            if self.settings.cache_ttl > 0:
                expiry = time.time() + self.settings.cache_ttl
                self._cache[cache_key] = (value, expiry)

            return value
        except HVACError as e:
            raise VaultError(
                f"Error retrieving secret '{path}#{key}' from Vault: {e}"
            ) from e
