from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.utils.config_types import Settings
from pytest_analyzer.utils.configuration import ConfigurationManager
from pytest_analyzer.utils.vault_manager import VaultError


@pytest.fixture
def mock_vault_manager():
    """Fixture to mock the VaultSecretManager."""
    with patch(
        "pytest_analyzer.utils.configuration.VaultSecretManager"
    ) as mock_manager_cls:
        mock_instance = MagicMock()

        def get_secret_side_effect(path, key, version=None):
            if path == "llm/creds" and key == "openai_api_key":
                return "vault-retrieved-api-key"
            if path == "mcp/config" and key == "auth_token":
                return "vault-retrieved-auth-token"
            raise VaultError(f"Secret not found for {path}#{key}")

        mock_instance.get_secret.side_effect = get_secret_side_effect
        mock_manager_cls.return_value = mock_instance
        yield mock_instance


def test_vault_secrets_are_resolved(mock_vault_manager):
    """Test that vault:// URIs are correctly resolved into secret values."""
    manager = ConfigurationManager(settings_cls=Settings)

    # Simulate a loaded config with vault URIs
    manager._config = {
        "llm_api_key": "vault://llm/creds#openai_api_key",
        "mcp": {
            "auth_token": "vault://mcp/config#auth_token",
            "http_port": 8000,
        },
        "vault": {
            "enabled": True,
            "url": "http://fake-vault:8200",
            "token": "fake-token",
        },
    }
    manager._loaded = True

    settings = manager.get_settings()

    # Check that the mock manager was called correctly
    assert mock_vault_manager.get_secret.call_count == 2
    mock_vault_manager.get_secret.assert_any_call(
        path="llm/creds", key="openai_api_key", version=None
    )
    mock_vault_manager.get_secret.assert_any_call(
        path="mcp/config", key="auth_token", version=None
    )

    # Check that the settings object has the resolved values
    assert settings.llm_api_key == "vault-retrieved-api-key"
    assert settings.mcp.auth_token == "vault-retrieved-auth-token"
    assert settings.mcp.http_port == 8000  # Unchanged


def test_vault_disabled(mock_vault_manager):
    """Test that secrets are not resolved if vault.enabled is false."""
    manager = ConfigurationManager(settings_cls=Settings)
    uri = "vault://llm/creds#openai_api_key"
    manager._config = {
        "llm_api_key": uri,
        "vault": {"enabled": False},
    }
    manager._loaded = True

    settings = manager.get_settings()

    # Vault manager should not have been used
    mock_vault_manager.get_secret.assert_not_called()
    # The URI should remain unresolved
    assert settings.llm_api_key == uri


def test_invalid_vault_uri(mock_vault_manager):
    """Test that an invalid vault URI is ignored and returned as-is."""
    manager = ConfigurationManager(settings_cls=Settings)
    invalid_uri = "vault://missing-key-separator"
    manager._config = {
        "llm_api_key": invalid_uri,
        "vault": {
            "enabled": True,
            "url": "http://fake-vault:8200",
            "token": "fake-token",
        },
    }
    manager._loaded = True

    settings = manager.get_settings()

    mock_vault_manager.get_secret.assert_not_called()
    assert settings.llm_api_key == invalid_uri


def test_vault_secret_retrieval_failure(mock_vault_manager):
    """Test that a failure to retrieve a secret leaves the URI in place."""
    mock_vault_manager.get_secret.side_effect = VaultError("Permission Denied")
    manager = ConfigurationManager(settings_cls=Settings)
    uri = "vault://llm/creds#openai_api_key"
    manager._config = {
        "llm_api_key": uri,
        "vault": {
            "enabled": True,
            "url": "http://fake-vault:8200",
            "token": "fake-token",
        },
    }
    manager._loaded = True

    settings = manager.get_settings()

    mock_vault_manager.get_secret.assert_called_once()
    # The URI should remain unresolved on failure
    assert settings.llm_api_key == uri


def test_vault_config_validation_failure():
    """Test that Vault integration is skipped if Vault config is invalid."""
    manager = ConfigurationManager(settings_cls=Settings)
    uri = "vault://llm/creds#openai_api_key"
    manager._config = {
        "llm_api_key": uri,
        "vault": {
            "enabled": True,
            # Missing URL and token, which is invalid
        },
    }
    manager._loaded = True

    # Vault validation should fail, but the configuration should fall back gracefully
    # The uri should remain unresolved, and the settings should use defaults where needed
    # Since vault:// URIs are not valid strings for most settings, settings should fall back to defaults
    settings = manager.get_settings()
    assert settings is not None
    # Since the vault URI couldn't be resolved and it's not a valid API key, it should fallback to default (None)
    assert settings.llm_api_key is None

    # A more direct test: check that the resolver returns the config unchanged when vault config is invalid
    resolved_config = manager._resolve_vault_secrets(manager._config)
    assert resolved_config["llm_api_key"] == uri


def test_vault_uri_in_list(mock_vault_manager):
    """Test that vault URIs are resolved when inside a list."""
    manager = ConfigurationManager(settings_cls=Settings)
    manager._config = {
        "pytest_args": [
            "--api-key",
            "vault://llm/creds#openai_api_key",
            "--some-other-arg",
        ],
        "vault": {
            "enabled": True,
            "url": "http://fake-vault:8200",
            "token": "fake-token",
        },
    }
    manager._loaded = True

    settings = manager.get_settings()

    mock_vault_manager.get_secret.assert_called_once_with(
        path="llm/creds", key="openai_api_key", version=None
    )
    assert settings.pytest_args == [
        "--api-key",
        "vault-retrieved-api-key",
        "--some-other-arg",
    ]
