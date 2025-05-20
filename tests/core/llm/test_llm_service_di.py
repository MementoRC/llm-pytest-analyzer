"""
Tests for LLM service dependency injection and container integration.

This module tests how LLM services are registered, resolved, and
configured through the dependency injection container.
"""

import os
from unittest.mock import MagicMock, patch

from pytest_analyzer.core.di import Container, initialize_container
from pytest_analyzer.core.di.service_collection import (
    ServiceCollection,
    _create_llm_service,
)
from pytest_analyzer.core.llm.llm_service_factory import LLMProvider
from pytest_analyzer.core.llm.llm_service_protocol import LLMServiceProtocol
from pytest_analyzer.utils.settings import Settings


class TestLLMServiceDI:
    """Test suite for LLM service integration with the DI container."""

    @patch("pytest_analyzer.core.llm.llm_service_factory.detect_llm_client")
    def test_service_collection_llm_services(self, mock_detect_client):
        """Test that ServiceCollection configures LLM services correctly."""
        # Set up mocks
        mock_client = MagicMock()
        mock_detect_client.return_value = (mock_client, LLMProvider.ANTHROPIC)

        # Test with explicit client
        service_collection = ServiceCollection()
        explicit_client = MagicMock()
        service_collection.configure_llm_services(llm_client=explicit_client)

        # Verify client detection was not called when explicit client is provided
        mock_detect_client.assert_not_called()

        # Create a new collection and test without explicit client
        service_collection = ServiceCollection()
        service_collection.configure_core_services().configure_llm_services()

        # Verify client detection was called
        mock_detect_client.assert_called_once()

    @patch("pytest_analyzer.core.llm.llm_service_factory.detect_llm_client")
    def test_custom_provider_override(self, mock_detect_client):
        """Test ServiceCollection with provider override."""
        # Set up mocks
        mock_client = MagicMock()
        mock_detect_client.return_value = (mock_client, LLMProvider.OPENAI)

        # Create service collection with provider override
        service_collection = ServiceCollection()
        service_collection.configure_llm_services(override_provider="openai")

        # Verify client detection was called with the right provider
        mock_detect_client.assert_called_once()
        assert mock_detect_client.call_args[1]["preferred_provider"] == "openai"

        # Reset mock for next test
        mock_detect_client.reset_mock()

        # Create with provider in settings
        settings = Settings()
        settings.llm_provider = "anthropic"
        container = Container()
        container.register_instance(Settings, settings)

        service_collection = ServiceCollection()
        service_collection.container = container
        service_collection.configure_llm_services()

        # Verify client detection respects settings preference
        assert mock_detect_client.call_args[1]["preferred_provider"] == "anthropic"

        # Reset mock for next test
        mock_detect_client.reset_mock()

        # Test override takes precedence over settings
        service_collection = ServiceCollection()
        service_collection.container = container
        service_collection.configure_llm_services(override_provider="azure")

        # Verify override trumps settings
        assert mock_detect_client.call_args[1]["preferred_provider"] == "azure"

    @patch("pytest_analyzer.core.llm.llm_service_factory.detect_llm_client")
    def test_fallback_settings_respected(self, mock_detect_client):
        """Test that fallback settings are respected."""
        # Set up mocks
        mock_detect_client.return_value = (MagicMock(), LLMProvider.OPENAI)

        # Test with fallback enabled in settings
        settings = Settings()
        settings.use_fallback = True
        container = Container()
        container.register_instance(Settings, settings)

        service_collection = ServiceCollection()
        service_collection.container = container
        service_collection.configure_llm_services()

        # Verify fallback was enabled
        assert mock_detect_client.call_args[1]["fallback"] is True

        # Reset mock for next test
        mock_detect_client.reset_mock()

        # Test with fallback disabled in settings
        settings = Settings()
        settings.use_fallback = False
        container = Container()
        container.register_instance(Settings, settings)

        service_collection = ServiceCollection()
        service_collection.container = container
        service_collection.configure_llm_services()

        # Verify fallback was disabled
        assert mock_detect_client.call_args[1]["fallback"] is False

        # Reset mock for next test
        mock_detect_client.reset_mock()

        # Test with override - fallback should be disabled for explicit override
        settings = Settings()
        settings.use_fallback = True  # Enabled in settings
        container = Container()
        container.register_instance(Settings, settings)

        service_collection = ServiceCollection()
        service_collection.container = container
        service_collection.configure_llm_services(override_provider="azure")

        # Verify fallback is False when using override
        assert mock_detect_client.call_args[1]["fallback"] is False

    def test_llm_service_factory_function_success(self):
        """Test the _create_llm_service factory function with successful client detection."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-test-key"}):
            with patch(
                "pytest_analyzer.core.llm.llm_service_factory.detect_llm_client"
            ) as mock_detect_client:
                # Create a mock client
                mock_client = MagicMock()
                mock_client.__class__.__module__ = "anthropic.client"
                mock_detect_client.return_value = (mock_client, LLMProvider.ANTHROPIC)

                # Test with explicit settings
                settings = Settings()
                settings.llm_timeout = 120  # Custom timeout

                container = Container()
                container.register_instance(Settings, settings)

                # Call the factory function
                llm_service = _create_llm_service(container)

                # Verify detect_llm_client was called
                mock_detect_client.assert_called_once()

                # Verify timeout was used from settings
                assert llm_service.timeout_seconds == 120

    def test_llm_service_factory_function_import_error(self):
        """Test the _create_llm_service factory function with import error handling."""
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory.detect_llm_client",
            side_effect=ImportError("Module not found"),
        ) as mock_detect_client:
            # Create test environment
            settings = Settings()
            container = Container()
            container.register_instance(Settings, settings)

            # Should create service with default values despite import error

            # Mock the LLMService import to avoid the actual error import path
            with patch(
                "pytest_analyzer.core.di.service_collection.LLMService"
            ) as mock_service:
                mock_service.return_value = MagicMock()

                # Call the function but don't need to store it as we're just testing the calls
                _create_llm_service(container)

                # Verify LLMService was called - specific client None check moved to mock
                assert mock_service.call_count == 1

                # Verify attempt was made to catch the import error
                mock_detect_client.assert_called_once()

    def test_llm_service_factory_function_general_error(self):
        """Test the _create_llm_service factory function with general error handling."""
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory.detect_llm_client",
            side_effect=Exception("General error"),
        ) as mock_detect_client:
            # Create test environment
            settings = Settings()
            container = Container()
            container.register_instance(Settings, settings)

            # Mock the LLMService import to isolate testing
            with patch(
                "pytest_analyzer.core.di.service_collection.LLMService"
            ) as mock_service:
                mock_service.return_value = MagicMock()

                # Call the function but don't need to store it, testing the error handling
                _create_llm_service(container)

                # Verify LLMService was called as a fallback
                assert mock_service.call_count == 1

                # Verify attempt was made to handle the error
                mock_detect_client.assert_called_once()

    @patch("pytest_analyzer.core.llm.llm_service_factory.detect_llm_client")
    def test_container_initialization_with_llm(self, mock_detect_client):
        """Test initialization of the container with LLM services."""
        # Set up mocks
        mock_client = MagicMock()
        mock_client.__class__.__module__ = "anthropic.client"
        mock_detect_client.return_value = (mock_client, LLMProvider.ANTHROPIC)

        # Test with LLM enabled
        settings = Settings()
        settings.use_llm = True

        # Initialize container
        container = initialize_container(settings)

        # Verify LLM service was registered
        assert LLMServiceProtocol in container._registrations

        # Resolve and verify service has the client
        llm_service = container.resolve(LLMServiceProtocol)
        assert llm_service.llm_client is mock_client

        # Reset mock for next test
        mock_detect_client.reset_mock()

        # Test with LLM disabled
        settings = Settings()
        settings.use_llm = False

        # Initialize container
        container = initialize_container(settings)

        # LLM service should still be registered
        assert LLMServiceProtocol in container._registrations

        # Resolve LLM service directly to verify it has a client
        # The service itself should be available even if use_llm is False
        llm_service = container.resolve(LLMServiceProtocol)
        assert llm_service is not None

        # But DI services that depend on it should get None if use_llm is False
        from pytest_analyzer.core.analyzer_service_di import DIPytestAnalyzerService

        analyzer_service = container.resolve(DIPytestAnalyzerService)
        assert analyzer_service.llm_service is None
