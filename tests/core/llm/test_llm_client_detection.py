"""
Tests for the LLM client detection functionality.

This module tests the client detection and fallback mechanisms
for various LLM providers, ensuring proper initialization based
on settings and environment variables.
"""

import os
from unittest.mock import MagicMock, patch

from pytest_analyzer.core.di import Container
from pytest_analyzer.core.di.service_collection import (
    ServiceCollection,
)
from pytest_analyzer.core.llm.llm_service_factory import (
    LLMProvider,
    _try_initialize_client,
    detect_llm_client,
    determine_provider,
)
from pytest_analyzer.core.llm.llm_service_protocol import LLMServiceProtocol
from pytest_analyzer.utils.settings import Settings

# Mock imports for provider types that might not be available
Anthropic = type("Anthropic", (), {})  # Create a dummy class for isinstance checks
AzureOpenAI = type("AzureOpenAI", (), {})  # Create a dummy class for isinstance checks
Together = type("Together", (), {})  # Create a dummy class for isinstance checks


class TestLLMClientDetection:
    """Tests for LLM client detection and initialization."""

    @patch("pytest_analyzer.core.llm.llm_service_factory.Anthropic", Anthropic)
    @patch("pytest_analyzer.core.llm.llm_service_factory.AzureOpenAI", AzureOpenAI)
    @patch("pytest_analyzer.core.llm.llm_service_factory.Together", Together)
    def test_determine_provider(self):
        """Test provider determination from client objects."""
        # Create mock objects for each provider type
        anthropic_mock = MagicMock()
        anthropic_mock.__class__.__module__ = "anthropic.client"

        openai_mock = MagicMock()
        openai_mock.__class__.__module__ = "openai.client"

        azure_mock = MagicMock()
        azure_mock.__class__.__module__ = "openai.azure_client"

        together_mock = MagicMock()
        together_mock.__class__.__module__ = "together.client"

        ollama_mock = MagicMock()
        ollama_mock.__class__.__module__ = "ollama.client"

        custom_mock = MagicMock()
        custom_mock.__class__.__module__ = "custom.client"

        # Test each provider using module name detection
        assert determine_provider(anthropic_mock) == LLMProvider.ANTHROPIC
        assert determine_provider(openai_mock) == LLMProvider.OPENAI
        assert determine_provider(azure_mock) == LLMProvider.AZURE_OPENAI
        assert determine_provider(together_mock) == LLMProvider.TOGETHER
        assert determine_provider(ollama_mock) == LLMProvider.OLLAMA
        assert determine_provider(custom_mock) == LLMProvider.CUSTOM
        assert determine_provider(None) == LLMProvider.UNKNOWN

    @patch("pytest_analyzer.core.llm.llm_service_factory._try_initialize_client")
    def test_detect_llm_client_with_preferred_provider(self, mock_init_client):
        """Test client detection with a specified preferred provider."""
        # Set up the mock
        mock_init_client.return_value = MagicMock()

        # Test with explicit provider preference
        settings = Settings()
        client, provider = detect_llm_client(settings, preferred_provider="anthropic")

        # Verify attempt to initialize Anthropic client first
        assert mock_init_client.call_args_list[0][0][0] == LLMProvider.ANTHROPIC

    def test_detect_llm_client_from_settings(self):
        """Test client detection using provider specified in settings."""
        # Use a simpler approach to test behavior rather than implementation details

        with patch(
            "pytest_analyzer.core.llm.llm_service_factory._try_initialize_client"
        ) as mock_init:
            # Set up multiple side effects - first call returns None, second returns a mock client
            # This simulates a provider failing and falling back to the next one
            mock_client = MagicMock()
            mock_init.side_effect = [None, mock_client]

            # Test with provider in settings
            settings = Settings()
            settings.llm_provider = "azure"
            settings.use_fallback = True

            # Call the function
            client, provider = detect_llm_client(settings)

            # Verify the client was returned
            assert client is mock_client
            assert mock_init.call_count >= 1  # At least one provider was tried

    @patch("pytest_analyzer.core.llm.llm_service_factory._try_initialize_client")
    def test_fallback_behavior(self, mock_init_client):
        """Test fallback behavior when preferred provider fails."""

        # Setup: first provider fails, second succeeds
        def side_effect(provider, _):
            if provider == LLMProvider.ANTHROPIC:
                return None
            elif provider == LLMProvider.OPENAI:
                return MagicMock()

        mock_init_client.side_effect = side_effect

        # Test with fallback enabled
        settings = Settings()
        client, provider = detect_llm_client(
            settings, preferred_provider="anthropic", fallback=True
        )

        # Verify fallback was used
        assert provider == LLMProvider.OPENAI
        assert mock_init_client.call_count > 1

    @patch("pytest_analyzer.core.llm.llm_service_factory._try_initialize_client")
    def test_no_fallback_when_disabled(self, mock_init_client):
        """Test behavior when fallback is disabled and preferred provider fails."""
        # Setup: preferred provider fails
        mock_init_client.return_value = None

        # Test with fallback disabled
        settings = Settings()
        client, provider = detect_llm_client(
            settings, preferred_provider="anthropic", fallback=False
        )

        # Verify no fallback was attempted
        assert client is None
        assert provider is None
        assert mock_init_client.call_count == 1  # Only tried the preferred provider

    @patch(
        "pytest_analyzer.core.llm.llm_service_factory.Anthropic", new_callable=MagicMock
    )
    def test_anthropic_client_initialization(self, mock_anthropic):
        """Test Anthropic client initialization with API key."""
        # Set up the mock
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Test with API key in settings
        settings = Settings()
        settings.anthropic_api_key = "test-api-key"

        client = _try_initialize_client(LLMProvider.ANTHROPIC, settings)

        # Verify client was initialized with correct API key
        mock_anthropic.assert_called_once_with(api_key="test-api-key")
        assert client is mock_client

    @patch(
        "pytest_analyzer.core.llm.llm_service_factory.openai", new_callable=MagicMock
    )
    def test_openai_client_initialization(self, mock_openai):
        """Test OpenAI client initialization with API key."""
        # Set up the mock for OpenAI
        mock_client = MagicMock()
        mock_openai.OpenAI.return_value = mock_client

        # Test with API key in settings
        settings = Settings()
        settings.openai_api_key = "test-openai-key"

        client = _try_initialize_client(LLMProvider.OPENAI, settings)

        # Verify client was initialized with correct API key
        mock_openai.OpenAI.assert_called_once_with(api_key="test-openai-key")
        assert client is mock_client

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-test-key"})
    @patch(
        "pytest_analyzer.core.llm.llm_service_factory.Anthropic", new_callable=MagicMock
    )
    def test_api_key_from_environment(self, mock_anthropic):
        """Test using API key from environment variable."""
        # Set up the mock
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Test with API key in environment
        settings = Settings()  # No key in settings
        client = _try_initialize_client(LLMProvider.ANTHROPIC, settings)

        # Verify client was initialized with environment API key
        mock_anthropic.assert_called_once_with(api_key="env-test-key")
        assert client is mock_client

    def test_azure_openai_initialization(self):
        """Test Azure OpenAI client initialization."""
        # Use a direct patch approach to avoid fixture issues
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory.AZURE_OPENAI_AVAILABLE", True
        ):
            with patch(
                "pytest_analyzer.core.llm.llm_service_factory.AzureOpenAI"
            ) as mock_azure:
                # Set up the mock
                mock_client = MagicMock()
                mock_azure.return_value = mock_client

                # Test with Azure settings
                settings = Settings()
                settings.azure_api_key = "azure-api-key"
                settings.azure_endpoint = "https://azure-endpoint.com"
                settings.azure_api_version = "2023-06-01"

                client = _try_initialize_client(LLMProvider.AZURE_OPENAI, settings)

                # Verify client was initialized with correct parameters
                mock_azure.assert_called_once_with(
                    api_key="azure-api-key",
                    azure_endpoint="https://azure-endpoint.com",
                    api_version="2023-06-01",
                )
                assert client is mock_client

    def test_together_client_initialization(self):
        """Test Together.ai client initialization."""
        # Use a direct patch approach to avoid fixture issues
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory.TOGETHER_AVAILABLE", True
        ):
            with patch(
                "pytest_analyzer.core.llm.llm_service_factory.Together"
            ) as mock_together:
                # Set up the mock
                mock_client = MagicMock()
                mock_together.return_value = mock_client

                # Test with Together settings
                settings = Settings()
                settings.together_api_key = "together-api-key"

                client = _try_initialize_client(LLMProvider.TOGETHER, settings)

                # Verify client was initialized correctly
                mock_together.assert_called_once_with(api_key="together-api-key")
                assert client is mock_client

    def test_ollama_client_detection(self):
        """Test Ollama client detection with running service."""
        # Use a direct patch approach to avoid fixture issues
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory.OLLAMA_AVAILABLE", True
        ):
            with patch("socket.socket") as mock_socket:
                with patch(
                    "pytest_analyzer.core.llm.llm_service_factory.ollama"
                ) as mock_ollama:
                    # Set up the socket mock to simulate Ollama running
                    socket_instance = MagicMock()
                    mock_socket.return_value.__enter__.return_value = socket_instance
                    socket_instance.connect_ex.return_value = 0  # Connection successful

                    # Test with Ollama settings
                    settings = Settings()
                    settings.ollama_host = "localhost"
                    settings.ollama_port = 11434

                    client = _try_initialize_client(LLMProvider.OLLAMA, settings)

                    # Verify Ollama client was returned
                    assert client is mock_ollama

    def test_error_handling_in_client_initialization(self):
        """Test error handling during client initialization."""
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory.Anthropic"
        ) as mock_anthropic:
            # Simulate error during initialization
            mock_anthropic.side_effect = ValueError("API key error")

            # Test error handling
            settings = Settings()
            settings.anthropic_api_key = "invalid-key"

            # Should return None but not raise an exception
            client = _try_initialize_client(LLMProvider.ANTHROPIC, settings)
            assert client is None

    @patch("pytest_analyzer.core.llm.llm_service_factory.detect_llm_client")
    def test_integration_with_service_collection(self, mock_detect_client):
        """Test integration of client detection with the ServiceCollection."""
        # Setup mocks
        mock_client = MagicMock()
        mock_detect_client.return_value = (mock_client, LLMProvider.OPENAI)

        # Create settings with LLM enabled
        settings = Settings()
        settings.use_llm = True

        # Create a container and configure services
        container = Container()
        container.register_instance(Settings, settings)

        # Test the service collection configuring LLM services
        service_collection = ServiceCollection()
        service_collection.container = container
        service_collection.configure_llm_services()

        # Resolve the LLM service to trigger the factory function
        service_collection.build_container().resolve(LLMServiceProtocol)

        # Verify the client detection was called
        mock_detect_client.assert_called_once()

        # Verify an LLM service was registered with the container
        assert LLMServiceProtocol in container._registrations

    def test_multiple_provider_fallback_behavior(self):
        """Test fallback across multiple providers in priority order."""
        # Setup: Create a test environment for testing the fallback behavior
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory._try_initialize_client"
        ) as mock_init:
            # Configure the mock to fail for first provider but succeed for second
            def side_effect(provider, _):
                if provider == LLMProvider.ANTHROPIC:
                    return None
                elif provider == LLMProvider.OPENAI:
                    return MagicMock()
                return None

            mock_init.side_effect = side_effect

            # Case 1: Test with fallback enabled
            settings = Settings()
            settings.use_fallback = True

            client, provider = detect_llm_client(
                settings, preferred_provider="anthropic", fallback=True
            )

            # Verify that fallback worked - we should get an OpenAI client
            assert provider == LLMProvider.OPENAI
            assert mock_init.call_count >= 2

            # Reset the mock
            mock_init.reset_mock()
            mock_init.side_effect = side_effect

            # Case 2: Test fallback with provider from settings
            settings = Settings()
            settings.llm_provider = "anthropic"
            settings.use_fallback = True

            client, provider = detect_llm_client(settings)

            # Verify that we tried Anthropic then fell back to OpenAI
            assert provider == LLMProvider.OPENAI
            assert mock_init.call_count >= 2

    @patch.dict(
        os.environ,
        {
            "ANTHROPIC_API_KEY": "env-anthropic-key",
            "OPENAI_API_KEY": "env-openai-key",
            "AZURE_OPENAI_API_KEY": "env-azure-key",
            "AZURE_OPENAI_ENDPOINT": "https://env-azure-endpoint.com",
        },
    )
    def test_environment_variable_detection(self):
        """Test detection of API keys from multiple environment variables."""
        # Test Anthropic environment detection
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory.Anthropic"
        ) as mock_anthropic:
            mock_anthropic_client = MagicMock()
            mock_anthropic.return_value = mock_anthropic_client

            settings = Settings()  # No keys in settings
            client = _try_initialize_client(LLMProvider.ANTHROPIC, settings)

            mock_anthropic.assert_called_once_with(api_key="env-anthropic-key")
            assert client is mock_anthropic_client

        # Test OpenAI environment detection
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory.openai"
        ) as mock_openai:
            mock_openai_client = MagicMock()
            mock_openai.OpenAI.return_value = mock_openai_client

            settings = Settings()  # No keys in settings
            client = _try_initialize_client(LLMProvider.OPENAI, settings)

            mock_openai.OpenAI.assert_called_once_with(api_key="env-openai-key")
            assert client is mock_openai_client

        # Test Azure OpenAI environment detection
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory.AZURE_OPENAI_AVAILABLE", True
        ):
            with patch(
                "pytest_analyzer.core.llm.llm_service_factory.AzureOpenAI"
            ) as mock_azure:
                mock_azure_client = MagicMock()
                mock_azure.return_value = mock_azure_client

                settings = Settings()  # No keys in settings
                client = _try_initialize_client(LLMProvider.AZURE_OPENAI, settings)

                # Should use environment variables for both key and endpoint
                mock_azure.assert_called_once_with(
                    api_key="env-azure-key",
                    azure_endpoint="https://env-azure-endpoint.com",
                    api_version="2023-05-15",  # Default version
                )
                assert client is mock_azure_client

    def test_anthropic_provider_preference(self):
        """Test that Anthropic provider preference is respected."""
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory._try_initialize_client"
        ) as mock_init:
            # Setup to have all providers succeed
            mock_init.return_value = MagicMock()

            settings = Settings()
            settings.llm_provider = "anthropic"

            detect_llm_client(settings)

            # Verify attempt was made with Anthropic first
            assert len(mock_init.call_args_list) > 0
            assert mock_init.call_args_list[0][0][0] == LLMProvider.ANTHROPIC

    def test_openai_provider_preference(self):
        """Test that OpenAI provider preference is respected."""
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory._try_initialize_client"
        ) as mock_init:
            # Setup to have all providers succeed
            openai_client = MagicMock()

            # Set up the side effect to return clients for different providers
            def side_effect(provider, settings):
                if provider == LLMProvider.OPENAI:
                    return openai_client
                return None

            mock_init.side_effect = side_effect

            settings = Settings()
            settings.llm_provider = "openai"

            client, provider = detect_llm_client(settings)

            # Verify we got the right client
            assert client is openai_client
            assert provider == LLMProvider.OPENAI

            # Verify attempt was made with OpenAI
            assert any(
                call[0][0] == LLMProvider.OPENAI for call in mock_init.call_args_list
            )

    def test_azure_openai_provider_preference(self):
        """Test that Azure OpenAI provider preference is respected."""
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory._try_initialize_client"
        ) as mock_init:
            # Setup to have all providers succeed
            azure_client = MagicMock()

            # Set up the side effect to return clients for different providers
            def side_effect(provider, settings):
                if provider == LLMProvider.AZURE_OPENAI:
                    return azure_client
                return None

            mock_init.side_effect = side_effect

            settings = Settings()
            settings.llm_provider = "azure_openai"

            client, provider = detect_llm_client(settings)

            # Verify we got the right client
            assert client is azure_client
            assert provider == LLMProvider.AZURE_OPENAI

            # Verify attempt was made with Azure
            assert any(
                call[0][0] == LLMProvider.AZURE_OPENAI
                for call in mock_init.call_args_list
            )

    def test_azure_provider_preference_alternative_spelling(self):
        """Test that Azure provider preference is respected with alternative spelling."""
        with patch(
            "pytest_analyzer.core.llm.llm_service_factory._try_initialize_client"
        ) as mock_init:
            # Setup to have all providers succeed
            azure_client = MagicMock()

            # Set up the side effect to return clients for different providers
            def side_effect(provider, settings):
                if provider == LLMProvider.AZURE_OPENAI:
                    return azure_client
                return None

            mock_init.side_effect = side_effect

            settings = Settings()
            settings.llm_provider = "azure"  # Alternative spelling

            client, provider = detect_llm_client(settings)

            # Verify we got the right client
            assert client is azure_client
            assert provider == LLMProvider.AZURE_OPENAI

            # Verify attempt was made with Azure
            assert any(
                call[0][0] == LLMProvider.AZURE_OPENAI
                for call in mock_init.call_args_list
            )
