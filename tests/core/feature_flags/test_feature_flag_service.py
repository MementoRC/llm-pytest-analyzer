"""Unit tests for the FlagsmithFeatureFlagService."""

from unittest.mock import MagicMock, patch

from pytest_analyzer.core.feature_flags.feature_flag_service import (
    FlagsmithFeatureFlagService,
)
from pytest_analyzer.utils.config_types import FeatureFlagSettings


class TestFlagsmithFeatureFlagService:
    """Test cases for FlagsmithFeatureFlagService."""

    @patch("pytest_analyzer.core.feature_flags.feature_flag_service.Flagsmith")
    def test_initialization_when_enabled(self, mock_flagsmith_class):
        """Test that the service initializes Flagsmith client when enabled with valid key."""
        mock_client_instance = MagicMock()
        mock_flagsmith_class.return_value = mock_client_instance

        settings = FeatureFlagSettings(
            enabled=True,
            environment_key="test_env_key",
            api_url="https://edge.api.flagsmith.com/api/v1/",
            enable_local_evaluation=True,
            environment_refresh_interval_seconds=60,
            enable_analytics=False,
        )

        service = FlagsmithFeatureFlagService(settings)

        # Verify that Flagsmith was initialized with the correct parameters
        mock_flagsmith_class.assert_called_once_with(
            environment_key="test_env_key",
            api_url="https://edge.api.flagsmith.com/api/v1/",
            enable_local_evaluation=True,
            environment_refresh_interval_seconds=60,
            enable_analytics=False,
        )
        assert service._flagsmith_client is mock_client_instance

    def test_initialization_when_disabled(self):
        """Test that the service doesn't initialize Flagsmith client when disabled."""
        settings = FeatureFlagSettings(enabled=False)

        service = FlagsmithFeatureFlagService(settings)

        assert service._flagsmith_client is None

    def test_initialization_enabled_but_no_key(self):
        """Test that the service doesn't initialize when enabled but no environment key."""
        settings = FeatureFlagSettings(enabled=True, environment_key=None)

        service = FlagsmithFeatureFlagService(settings)

        assert service._flagsmith_client is None

    @patch("pytest_analyzer.core.feature_flags.feature_flag_service.Flagsmith")
    def test_is_feature_enabled_returns_true(self, mock_flagsmith_class):
        """Test that is_feature_enabled returns True when the flag is enabled."""
        mock_client_instance = MagicMock()
        mock_flagsmith_class.return_value = mock_client_instance

        # Mock the flags object that the client would return
        mock_flags = MagicMock()
        mock_flags.is_feature_enabled.return_value = True
        mock_client_instance.get_environment_flags.return_value = mock_flags

        settings = FeatureFlagSettings(enabled=True, environment_key="test_key")
        service = FlagsmithFeatureFlagService(settings)

        result = service.is_feature_enabled("some_feature")

        assert result is True
        mock_client_instance.get_environment_flags.assert_called_once()
        mock_flags.is_feature_enabled.assert_called_once_with("some_feature")

    @patch("pytest_analyzer.core.feature_flags.feature_flag_service.Flagsmith")
    def test_is_feature_enabled_returns_false(self, mock_flagsmith_class):
        """Test that is_feature_enabled returns False when the flag is disabled."""
        mock_client_instance = MagicMock()
        mock_flagsmith_class.return_value = mock_client_instance

        # Mock the flags object that the client would return
        mock_flags = MagicMock()
        mock_flags.is_feature_enabled.return_value = False
        mock_client_instance.get_environment_flags.return_value = mock_flags

        settings = FeatureFlagSettings(enabled=True, environment_key="test_key")
        service = FlagsmithFeatureFlagService(settings)

        result = service.is_feature_enabled("some_feature")

        assert result is False
        mock_flags.is_feature_enabled.assert_called_once_with("some_feature")

    def test_is_feature_enabled_with_no_client(self):
        """Test that is_feature_enabled returns False when no client is initialized."""
        settings = FeatureFlagSettings(enabled=False)
        service = FlagsmithFeatureFlagService(settings)

        result = service.is_feature_enabled("some_feature")

        assert result is False

    @patch("pytest_analyzer.core.feature_flags.feature_flag_service.Flagsmith")
    def test_is_feature_enabled_with_identity(self, mock_flagsmith_class):
        """Test that is_feature_enabled works with user identity."""
        mock_client_instance = MagicMock()
        mock_flagsmith_class.return_value = mock_client_instance

        # Mock the flags object for identity
        mock_flags = MagicMock()
        mock_flags.is_feature_enabled.return_value = True
        mock_client_instance.get_identity_flags.return_value = mock_flags

        settings = FeatureFlagSettings(enabled=True, environment_key="test_key")
        service = FlagsmithFeatureFlagService(settings)

        result = service.is_feature_enabled("some_feature", identity="user123")

        assert result is True
        mock_client_instance.get_identity_flags.assert_called_once_with(
            identifier="user123"
        )
        mock_flags.is_feature_enabled.assert_called_once_with("some_feature")

    @patch("pytest_analyzer.core.feature_flags.feature_flag_service.Flagsmith")
    def test_get_feature_value(self, mock_flagsmith_class):
        """Test that get_feature_value returns the correct value."""
        mock_client_instance = MagicMock()
        mock_flagsmith_class.return_value = mock_client_instance

        # Mock the flags and feature objects
        mock_feature = MagicMock()
        mock_feature.value = "test_value"
        mock_flags = MagicMock()
        mock_flags.get_feature.return_value = mock_feature
        mock_client_instance.get_environment_flags.return_value = mock_flags

        settings = FeatureFlagSettings(enabled=True, environment_key="test_key")
        service = FlagsmithFeatureFlagService(settings)

        result = service.get_feature_value("some_feature")

        assert result == "test_value"
        mock_flags.get_feature.assert_called_once_with("some_feature")

    @patch("pytest_analyzer.core.feature_flags.feature_flag_service.Flagsmith")
    def test_get_all_flags(self, mock_flagsmith_class):
        """Test that get_all_flags returns all feature flags."""
        mock_client_instance = MagicMock()
        mock_flagsmith_class.return_value = mock_client_instance

        # Mock flag objects
        mock_flag1 = MagicMock()
        mock_flag1.feature.name = "feature1"
        mock_flag1.enabled = True
        mock_flag1.feature_state_value = "value1"

        mock_flag2 = MagicMock()
        mock_flag2.feature.name = "feature2"
        mock_flag2.enabled = False
        mock_flag2.feature_state_value = "value2"

        mock_flags = [mock_flag1, mock_flag2]
        mock_client_instance.get_environment_flags.return_value = mock_flags

        settings = FeatureFlagSettings(enabled=True, environment_key="test_key")
        service = FlagsmithFeatureFlagService(settings)

        result = service.get_all_flags()

        expected = {
            "feature1": {"enabled": True, "value": "value1"},
            "feature2": {"enabled": False, "value": "value2"},
        }
        assert result == expected

    @patch("pytest_analyzer.core.feature_flags.feature_flag_service.Flagsmith")
    def test_service_is_resilient_to_client_errors(self, mock_flagsmith_class):
        """Test that the service handles client errors gracefully."""
        mock_client_instance = MagicMock()
        mock_flagsmith_class.return_value = mock_client_instance

        # Simulate an error when trying to get flags from the client
        mock_client_instance.get_environment_flags.side_effect = Exception("API error")

        settings = FeatureFlagSettings(enabled=True, environment_key="test_key")
        service = FlagsmithFeatureFlagService(settings)

        # The service should handle the error gracefully
        assert service.is_feature_enabled("failing_feature") is False
        assert service.get_feature_value("failing_feature") is None
        assert service.get_all_flags() == {}

    @patch("pytest_analyzer.core.feature_flags.feature_flag_service.Flagsmith")
    def test_initialization_handles_flagsmith_errors(self, mock_flagsmith_class):
        """Test that initialization handles Flagsmith client creation errors gracefully."""
        # Simulate an error during Flagsmith client instantiation
        mock_flagsmith_class.side_effect = Exception("Flagsmith connection failed")

        settings = FeatureFlagSettings(enabled=True, environment_key="test_key")
        service = FlagsmithFeatureFlagService(settings)

        # The service should not have a client and should handle requests gracefully
        assert service._flagsmith_client is None
        assert service.is_feature_enabled("any_feature") is False
