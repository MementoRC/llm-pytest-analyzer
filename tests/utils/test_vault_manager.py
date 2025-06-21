import time
from unittest.mock import patch

import pytest
from hvac.exceptions import Forbidden, InvalidPath

from pytest_analyzer.utils.config_types import VaultSettings
from pytest_analyzer.utils.vault_manager import VaultError, VaultSecretManager


@pytest.fixture
def vault_settings_token():
    """Fixture for VaultSettings with token auth."""
    return VaultSettings(
        enabled=True,
        url="http://127.0.0.1:8200",
        auth_method="token",
        token="test-token",
        mount_point="secret",
        cache_ttl=300,
    )


@pytest.fixture
def vault_settings_approle():
    """Fixture for VaultSettings with AppRole auth."""
    return VaultSettings(
        enabled=True,
        url="http://127.0.0.1:8200",
        auth_method="approle",
        role_id="test-role-id",
        secret_id="test-secret-id",
        mount_point="secret",
    )


@patch("hvac.Client")
def test_init_disabled(mock_hvac_client):
    """Test that VaultSecretManager raises an error if initialized while disabled."""
    settings = VaultSettings(enabled=False)
    with pytest.raises(VaultError, match="VaultSecretManager cannot be initialized"):
        VaultSecretManager(settings)


@patch("hvac.Client")
def test_connect_token_auth_success(mock_hvac_client, vault_settings_token):
    """Test successful connection and authentication using a token."""
    mock_client_instance = mock_hvac_client.return_value
    mock_client_instance.is_authenticated.return_value = True

    manager = VaultSecretManager(vault_settings_token)
    # Accessing the client property triggers the connection
    client = manager.client

    mock_hvac_client.assert_called_once_with(
        url=str(vault_settings_token.url), timeout=vault_settings_token.timeout
    )
    assert client.token == vault_settings_token.token
    assert manager._client is not None


@patch("hvac.api.auth_methods.AppRole")
@patch("hvac.Client")
def test_connect_approle_auth_success(
    mock_hvac_client, mock_approle_auth, vault_settings_approle
):
    """Test successful connection and authentication using AppRole."""
    mock_client_instance = mock_hvac_client.return_value
    mock_client_instance.is_authenticated.return_value = True
    mock_approle_auth.return_value.login.return_value = {}

    manager = VaultSecretManager(vault_settings_approle)
    _ = manager.client  # Trigger connection

    mock_hvac_client.assert_called_once_with(
        url=str(vault_settings_approle.url), timeout=vault_settings_approle.timeout
    )
    mock_approle_auth.assert_called_once_with(mock_client_instance.adapter)
    mock_approle_auth.return_value.login.assert_called_once_with(
        role_id=vault_settings_approle.role_id,
        secret_id=vault_settings_approle.secret_id,
        use_token=True,
    )


@patch("hvac.Client")
def test_connect_auth_failure(mock_hvac_client, vault_settings_token):
    """Test that a VaultError is raised if authentication fails."""
    mock_client_instance = mock_hvac_client.return_value
    mock_client_instance.is_authenticated.return_value = False

    manager = VaultSecretManager(vault_settings_token)
    with pytest.raises(VaultError, match="Vault authentication failed"):
        _ = manager.client


@patch("hvac.Client")
def test_get_secret_success(mock_hvac_client, vault_settings_token):
    """Test successfully retrieving a secret."""
    mock_client_instance = mock_hvac_client.return_value
    mock_client_instance.is_authenticated.return_value = True
    mock_read_secret = mock_client_instance.secrets.kv.v2.read_secret_version
    mock_read_secret.return_value = {
        "data": {"data": {"api_key": "12345", "user": "test"}}
    }

    manager = VaultSecretManager(vault_settings_token)
    secret_value = manager.get_secret(path="myapp/config", key="api_key")

    assert secret_value == "12345"
    mock_read_secret.assert_called_once_with(
        path="myapp/config", mount_point="secret", version=None
    )


@patch("hvac.Client")
def test_get_secret_caching(mock_hvac_client, vault_settings_token):
    """Test that secrets are cached and cache is used on subsequent calls."""
    mock_client_instance = mock_hvac_client.return_value
    mock_client_instance.is_authenticated.return_value = True
    mock_read_secret = mock_client_instance.secrets.kv.v2.read_secret_version
    mock_read_secret.return_value = {"data": {"data": {"api_key": "12345"}}}

    manager = VaultSecretManager(vault_settings_token)

    # First call - should call Vault
    val1 = manager.get_secret(path="myapp/config", key="api_key")
    assert val1 == "12345"
    assert mock_read_secret.call_count == 1

    # Second call - should use cache
    val2 = manager.get_secret(path="myapp/config", key="api_key")
    assert val2 == "12345"
    assert mock_read_secret.call_count == 1  # Should not be called again


@patch("hvac.Client")
def test_get_secret_cache_expiration(mock_hvac_client, vault_settings_token):
    """Test that the cache expires and Vault is called again."""
    vault_settings_token.cache_ttl = 1  # 1 second TTL
    mock_client_instance = mock_hvac_client.return_value
    mock_client_instance.is_authenticated.return_value = True
    mock_read_secret = mock_client_instance.secrets.kv.v2.read_secret_version
    mock_read_secret.return_value = {"data": {"data": {"api_key": "12345"}}}

    manager = VaultSecretManager(vault_settings_token)

    # First call
    manager.get_secret(path="myapp/config", key="api_key")
    assert mock_read_secret.call_count == 1

    # Wait for cache to expire
    time.sleep(1.1)

    # Second call - should call Vault again
    manager.get_secret(path="myapp/config", key="api_key")
    assert mock_read_secret.call_count == 2


@patch("hvac.Client")
def test_get_secret_key_not_found(mock_hvac_client, vault_settings_token):
    """Test that VaultError is raised if the key is not in the secret data."""
    mock_client_instance = mock_hvac_client.return_value
    mock_client_instance.is_authenticated.return_value = True
    mock_read_secret = mock_client_instance.secrets.kv.v2.read_secret_version
    mock_read_secret.return_value = {"data": {"data": {"another_key": "value"}}}

    manager = VaultSecretManager(vault_settings_token)
    with pytest.raises(VaultError, match="Key 'api_key' not found"):
        manager.get_secret(path="myapp/config", key="api_key")


@patch("hvac.Client")
def test_get_secret_path_not_found(mock_hvac_client, vault_settings_token):
    """Test that VaultError is raised if the path is invalid."""
    mock_client_instance = mock_hvac_client.return_value
    mock_client_instance.is_authenticated.return_value = True
    mock_read_secret = mock_client_instance.secrets.kv.v2.read_secret_version
    mock_read_secret.side_effect = InvalidPath("No secret found at path")

    manager = VaultSecretManager(vault_settings_token)
    with pytest.raises(VaultError, match="Error retrieving secret"):
        manager.get_secret(path="invalid/path", key="api_key")


@patch("hvac.Client")
def test_get_secret_permission_denied(mock_hvac_client, vault_settings_token):
    """Test that VaultError is raised on permission denied."""
    mock_client_instance = mock_hvac_client.return_value
    mock_client_instance.is_authenticated.return_value = True
    mock_read_secret = mock_client_instance.secrets.kv.v2.read_secret_version
    mock_read_secret.side_effect = Forbidden("Permission denied")

    manager = VaultSecretManager(vault_settings_token)
    with pytest.raises(VaultError, match="Permission denied"):
        manager.get_secret(path="restricted/path", key="api_key")


@patch("hvac.Client")
def test_get_secret_with_version(mock_hvac_client, vault_settings_token):
    """Test retrieving a specific version of a secret."""
    mock_client_instance = mock_hvac_client.return_value
    mock_client_instance.is_authenticated.return_value = True
    mock_read_secret = mock_client_instance.secrets.kv.v2.read_secret_version
    mock_read_secret.return_value = {"data": {"data": {"api_key": "v2-key"}}}

    manager = VaultSecretManager(vault_settings_token)
    secret_value = manager.get_secret(path="myapp/config", key="api_key", version=2)

    assert secret_value == "v2-key"
    mock_read_secret.assert_called_once_with(
        path="myapp/config", mount_point="secret", version=2
    )
