"""
Tests for LLM services refactored to use BaseLLMService.

This module tests the integration between the refactored LLM services
and the BaseLLMService base class.
"""

from unittest.mock import MagicMock, patch

from src.pytest_analyzer.core.infrastructure.llm.base_llm_service import BaseLLMService
from src.pytest_analyzer.core.llm.async_llm_service import AsyncLLMService
from src.pytest_analyzer.core.llm.llm_service import LLMService


class TestLLMServiceBaseIntegration:
    """Tests for LLM service integration with BaseLLMService."""

    def test_llm_service_inherits_from_base(self):
        """Test that LLMService properly inherits from BaseLLMService."""
        assert issubclass(LLMService, BaseLLMService)

    def test_async_llm_service_inherits_from_base(self):
        """Test that AsyncLLMService properly inherits from BaseLLMService."""
        assert issubclass(AsyncLLMService, BaseLLMService)

    def test_generate_method_implementation(self):
        """Test that the generate method is properly implemented."""
        # Create a mock client
        mock_client = MagicMock()
        # Identify the mock_client as an Anthropic client for LLMService internal routing
        mock_client.__class__.__module__ = "anthropic"

        # Setup the expected response structure for an Anthropic-like client
        mock_message_content = MagicMock()
        mock_message_content.text = "Test response"
        mock_anthropic_response = MagicMock()
        mock_anthropic_response.content = [mock_message_content]
        mock_client.messages.create.return_value = mock_anthropic_response

        # Create service with mocked dependencies
        with (
            patch("src.pytest_analyzer.core.llm.llm_service.PromptBuilder"),
            patch("src.pytest_analyzer.core.llm.llm_service.ResponseParser"),
        ):
            service = LLMService(llm_client=mock_client)

            # Test the generate method
            response = service.generate("test prompt")
            assert response == "Test response"

    def test_base_llm_service_methods_available(self):
        """Test that base class methods are available in the service."""
        with patch("src.pytest_analyzer.core.llm.llm_service.PromptBuilder"):
            with patch("src.pytest_analyzer.core.llm.llm_service.ResponseParser"):
                service = LLMService()

                # Check that base class methods are available
                assert hasattr(service, "_prepare_messages")
                assert hasattr(service, "_get_system_prompt")
                assert hasattr(service, "generate")
                assert hasattr(service, "provider")
                assert hasattr(service, "settings")
                assert hasattr(service, "logger")

    def test_async_generate_method_implementation(self):
        """Test that the async generate method is properly implemented."""
        # Create a mock client
        mock_client = MagicMock()
        # Identify the mock_client as an Anthropic client for AsyncLLMService internal routing
        mock_client.__class__.__module__ = "anthropic"

        # Setup the expected response structure for an Anthropic-like client
        mock_message_content = MagicMock()
        mock_message_content.text = "Async test response"
        mock_anthropic_response = MagicMock()
        mock_anthropic_response.content = [mock_message_content]

        # mock_client.messages.create needs to be an async function
        async def mock_create(*args, **kwargs):
            return mock_anthropic_response

        mock_client.messages.create = mock_create
        # Create mocks for required dependencies
        mock_prompt_builder = MagicMock()
        mock_response_parser = MagicMock()

        # Create async service with mocked dependencies
        with (
            patch("src.pytest_analyzer.core.llm.async_llm_service.PromptBuilder"),
            patch("src.pytest_analyzer.core.llm.async_llm_service.ResponseParser"),
        ):
            service = AsyncLLMService(
                prompt_builder=mock_prompt_builder,
                response_parser=mock_response_parser,
                llm_client=mock_client,
            )

            # Test the generate method (sync wrapper for async implementation)
            response = service.generate("test prompt")
            assert response == "Async test response"

    def test_base_factory_pattern_elimination(self):
        """Test that code duplication has been eliminated through base class usage."""
        # Create mocks for required dependencies for AsyncLLMService
        mock_async_prompt_builder = MagicMock()
        mock_async_response_parser = MagicMock()

        # Create both services with mocked dependencies
        with (
            patch("src.pytest_analyzer.core.llm.llm_service.PromptBuilder"),
            patch("src.pytest_analyzer.core.llm.llm_service.ResponseParser"),
        ):
            sync_service = LLMService()

        with (
            patch("src.pytest_analyzer.core.llm.async_llm_service.PromptBuilder"),
            patch("src.pytest_analyzer.core.llm.async_llm_service.ResponseParser"),
        ):
            async_service = AsyncLLMService(
                prompt_builder=mock_async_prompt_builder,
                response_parser=mock_async_response_parser,
            )

        # Both should have the same base class attributes
        # Note: 'model' and 'timeout' are set in __init__ based on args/settings,
        # so checking for their existence is sufficient here.
        base_attrs = ["provider", "settings", "logger"]
        for attr in base_attrs:
            assert hasattr(sync_service, attr)
            assert hasattr(async_service, attr)

        # Both should implement the generate method
        assert hasattr(sync_service, "generate")
        assert hasattr(async_service, "generate")

    def test_settings_integration_with_base_class(self):
        """Test that settings are properly passed to and used by the base class."""
        from src.pytest_analyzer.utils.config_types import Settings

        settings = Settings()
        settings.llm_model = "test-model"
        settings.llm_timeout = 120

        with patch("src.pytest_analyzer.core.llm.llm_service.PromptBuilder"):
            with patch("src.pytest_analyzer.core.llm.llm_service.ResponseParser"):
                service = LLMService(settings=settings)

                # Check that base class got the settings
                assert service.settings is settings
                assert service.model == "test-model"
                assert service.timeout == 120
