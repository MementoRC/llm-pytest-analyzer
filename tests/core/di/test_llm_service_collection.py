"""
Tests for LLM service integration with the ServiceCollection class.

This module specifically tests the LLM service configuration and detection
functionality in the ServiceCollection class.
"""

from unittest.mock import MagicMock, patch

from src.pytest_analyzer.core.di.service_collection import ServiceCollection
from src.pytest_analyzer.core.llm.backward_compat import LLMService
from src.pytest_analyzer.core.llm.llm_service_protocol import LLMServiceProtocol
from src.pytest_analyzer.utils.settings import Settings


class TestLLMServiceCollection:
    """Tests for LLM service integration with ServiceCollection."""

    def test_configure_llm_services_with_direct_client(self):
        """Test configuring LLM services with a directly provided client."""
        # Create a service collection and a mock client
        services = ServiceCollection()
        mock_client = MagicMock()

        # Configure with the mock client
        result = services.configure_llm_services(llm_client=mock_client)

        # Verify fluent API returns self
        assert result is services

        # Resolve the LLM service
        llm_service = services.container.resolve(LLMServiceProtocol)
        assert isinstance(llm_service, LLMServiceProtocol)
        assert llm_service.llm_client is mock_client

    def test_configure_llm_services_with_provider_override(self):
        """Test configuring LLM services with a provider override."""
        # Use a direct patch approach to avoid issues with import paths
        with patch(
            "src.pytest_analyzer.core.llm.llm_service_factory.detect_llm_client"
        ) as mock_detect:
            # Setup mock detection to return a client
            mock_client = MagicMock()
            mock_detect.return_value = (mock_client, MagicMock())

            # Create a service collection
            services = ServiceCollection()

            # Configure with provider override
            services.configure_llm_services(override_provider="anthropic")

            # Verify detect_llm_client was called with the right provider
            mock_detect.assert_called_once()
            assert mock_detect.call_args[1]["preferred_provider"] == "anthropic"

            # Verify service was registered with expected timeout
            llm_service = services.container.resolve(LLMServiceProtocol)
            assert isinstance(llm_service, LLMServiceProtocol)

    def test_configure_llm_services_with_settings_provider(self):
        """Test configuring LLM services using settings provider."""
        # Use a direct patch approach to avoid issues with import paths
        with patch(
            "src.pytest_analyzer.core.llm.llm_service_factory.detect_llm_client"
        ) as mock_detect:
            # Setup mock detection to return a client
            mock_client = MagicMock()
            mock_detect.return_value = (mock_client, MagicMock())

            # Create settings with a preferred provider
            settings = Settings()
            settings.llm_provider = "openai"

            # Create a service collection with those settings
            services = ServiceCollection()
            services.add_singleton(Settings, settings)

            # Configure LLM services
            services.configure_llm_services()

            # Verify detect_llm_client was called with settings provider
            mock_detect.assert_called_once()
            assert mock_detect.call_args[1]["preferred_provider"] == "openai"
            assert mock_detect.call_args[1]["fallback"] is True

            # Verify service was registered
            llm_service = services.container.resolve(LLMServiceProtocol)
            assert isinstance(llm_service, LLMServiceProtocol)

    def test_configure_llm_services_fallback_control(self):
        """Test fallback control in LLM service configuration."""
        # Use a direct patch approach to avoid issues with import paths
        with patch(
            "src.pytest_analyzer.core.llm.llm_service_factory.detect_llm_client"
        ) as mock_detect:
            # Setup mock detection to return a client
            mock_client = MagicMock()
            mock_detect.return_value = (mock_client, MagicMock())

            # Create settings with fallback disabled
            settings = Settings()
            settings.llm_provider = "anthropic"
            settings.use_fallback = False

            # Create a service collection with those settings
            services = ServiceCollection()
            services.add_singleton(Settings, settings)

            # Configure LLM services
            services.configure_llm_services()

            # Verify detect_llm_client was called with fallback disabled
            mock_detect.assert_called_once()
            assert mock_detect.call_args[1]["preferred_provider"] == "anthropic"
            assert mock_detect.call_args[1]["fallback"] is False

    def test_create_llm_service_factory_function(self):
        """Test the _create_llm_service factory function in service collection."""
        # Import the function directly for testing
        from src.pytest_analyzer.core.di.service_collection import _create_llm_service

        # Use a direct patch approach to avoid issues with import paths
        with patch(
            "src.pytest_analyzer.core.llm.llm_service_factory.detect_llm_client"
        ) as mock_detect:
            # Setup mock to return a client
            mock_client = MagicMock()
            mock_detect.return_value = (mock_client, MagicMock())

            # Create a container with settings
            services = ServiceCollection()
            settings = Settings()
            settings.llm_provider = "anthropic"
            settings.llm_timeout = 90
            services.add_singleton(Settings, settings)
            container = services.build_container()

            # Call the factory function
            llm_service = _create_llm_service(container)

            # Verify detect_llm_client was called correctly
            mock_detect.assert_called_once()
            assert mock_detect.call_args[1]["preferred_provider"] == "anthropic"

            # Verify service was created correctly
            assert isinstance(llm_service, LLMService)
            assert llm_service.timeout_seconds == 90

    def test_integration_with_core_services(self):
        """Test integration of LLM services with core services configuration."""
        # Use a direct patch approach to avoid issues with import paths
        with patch(
            "src.pytest_analyzer.core.llm.llm_service_factory.detect_llm_client"
        ) as mock_detect:
            # Setup mock to return a client
            mock_client = MagicMock()
            mock_detect.return_value = (mock_client, MagicMock())

            # Create a service collection with configured core services
            services = ServiceCollection()
            services.configure_core_services()

            # Verify LLM service was created
            llm_service = services.container.resolve(LLMServiceProtocol)
            assert isinstance(llm_service, LLMService)

    def test_handling_no_client_detected(self):
        """Test behavior when no LLM client could be detected."""
        # Use a direct patch approach to avoid issues with import paths
        with patch(
            "src.pytest_analyzer.core.llm.llm_service_factory.detect_llm_client"
        ) as mock_detect:
            # Setup mock to return no client
            mock_detect.return_value = (None, None)

            # Create and configure services
            services = ServiceCollection()
            services.configure_llm_services()

            # A service should still be created but with no client
            llm_service = services.container.resolve(LLMServiceProtocol)
            assert isinstance(llm_service, LLMService)
            assert llm_service.llm_client is None

    def test_error_handling_in_configuration(self):
        """Test error handling during LLM service configuration."""
        # Use a direct patch approach to avoid issues with import paths
        with patch(
            "src.pytest_analyzer.core.llm.llm_service_factory.detect_llm_client"
        ) as mock_detect:
            # Setup mock to raise an exception
            mock_detect.side_effect = RuntimeError("Connection error")

            # Create and configure services - should not raise exception
            services = ServiceCollection()
            services.configure_llm_services()

            # A service should still be created with no client
            llm_service = services.container.resolve(LLMServiceProtocol)
            assert isinstance(llm_service, LLMService)
            assert llm_service.llm_client is None
