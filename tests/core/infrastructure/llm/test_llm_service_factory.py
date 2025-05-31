"""Tests for LLMServiceFactory implementation."""

from unittest.mock import Mock, patch

import pytest

from pytest_analyzer.core.infrastructure.llm.anthropic_service import AnthropicService
from pytest_analyzer.core.infrastructure.llm.llm_service_factory import (
    LLMServiceFactory,
)
from pytest_analyzer.core.infrastructure.llm.mock_service import MockLLMService
from pytest_analyzer.core.infrastructure.llm.openai_service import OpenAIService
from pytest_analyzer.core.models.failure_analysis import FailureAnalysis
from pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure
from pytest_analyzer.utils.config_types import Settings


class TestLLMServiceFactory:
    """Test cases for LLMServiceFactory."""

    def test_init_registers_default_services(self):
        """Test that _register_default_services correctly registers all LLM services."""
        factory = LLMServiceFactory()

        # Verify all default services are registered
        assert factory.get_implementation("openai") == OpenAIService
        assert factory.get_implementation("anthropic") == AnthropicService
        assert factory.get_implementation("mock") == MockLLMService

    def test_create_returns_correct_service_type(self):
        """Test that create returns the correct service type based on provider_type."""
        factory = LLMServiceFactory()

        # Test OpenAI service creation
        openai_service = factory.create("openai")
        assert isinstance(openai_service, OpenAIService)

        # Test Anthropic service creation
        anthropic_service = factory.create("anthropic")
        assert isinstance(anthropic_service, AnthropicService)

        # Test Mock service creation
        mock_service = factory.create("mock")
        assert isinstance(mock_service, MockLLMService)

    def test_create_uses_settings_for_provider_type(self):
        """Test that create uses settings to determine provider_type when not specified."""
        settings = Mock()
        settings.llm_provider = "anthropic"

        factory = LLMServiceFactory(settings)
        service = factory.create()

        assert isinstance(service, AnthropicService)

    def test_create_defaults_to_openai_when_no_settings(self):
        """Test that create defaults to OpenAI when no settings are provided."""
        factory = LLMServiceFactory()
        service = factory.create()

        assert isinstance(service, OpenAIService)

    def test_create_passes_provider_and_settings_to_service(self):
        """Test that create correctly passes provider and settings to the service constructor."""
        settings = Settings()
        mock_provider = Mock()

        with patch.object(OpenAIService, "__init__", return_value=None) as mock_init:
            factory = LLMServiceFactory(settings)
            factory.create("openai", provider=mock_provider)

            mock_init.assert_called_once_with(provider=mock_provider, settings=settings)

    def test_create_handles_unsupported_provider_type(self):
        """Test error handling for unsupported provider types."""
        from pytest_analyzer.core.errors import LLMServiceError

        factory = LLMServiceFactory()

        with pytest.raises(LLMServiceError, match="Creating LLM service failed"):
            factory.create("unsupported")

    @patch("pytest_analyzer.core.infrastructure.llm.llm_service_factory.error_context")
    def test_create_uses_error_context(self, mock_error_context):
        """Test that create uses error_context for error handling."""
        factory = LLMServiceFactory()
        mock_error_context.return_value.__enter__ = Mock()
        mock_error_context.return_value.__exit__ = Mock(return_value=False)

        factory.create("mock")

        # The actual call in llm_service_factory.py is:
        # with error_context("Creating LLM service", self.logger, LLMServiceError):
        from pytest_analyzer.core.errors import LLMServiceError

        mock_error_context.assert_called_once_with(
            "Creating LLM service", factory.logger, LLMServiceError
        )


class TestOpenAIService:
    """Test cases for OpenAIService."""

    def test_send_prompt_returns_mock_response(self):
        """Test that send_prompt method works with mock provider."""
        mock_provider = Mock()
        mock_provider.send_request.return_value = "Test response"

        service = OpenAIService(provider=mock_provider)
        result = service.send_prompt("Test prompt")

        assert result == "Test response"
        mock_provider.send_request.assert_called_once_with("Test prompt")

    def test_analyze_failure_returns_failure_analysis(self):
        """Test that analyze_failure returns a FailureAnalysis object."""
        mock_provider = Mock()
        mock_provider.send_request.return_value = "Analysis result"

        failure = PytestFailure(
            test_name="test_example",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="Test failed",
            traceback="Traceback here",
        )

        service = OpenAIService(provider=mock_provider)
        result = service.analyze_failure(failure)

        assert isinstance(result, FailureAnalysis)
        assert result.failure == failure
        assert result.root_cause == "Analysis result"
        assert result.error_type == "OpenAI"
        assert result.confidence == 0.8

    def test_suggest_fixes_returns_fix_suggestions(self):
        """Test that suggest_fixes returns a list of FixSuggestion objects."""
        mock_provider = Mock()
        mock_provider.send_request.return_value = "Fix suggestion"

        failure = PytestFailure(
            test_name="test_example",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="Test failed",
            traceback="Traceback here",
        )

        service = OpenAIService(provider=mock_provider)
        result = service.suggest_fixes(failure)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], FixSuggestion)
        assert result[0].failure == failure
        assert result[0].suggestion == "Fix suggestion"
        assert result[0].confidence == 0.7


class TestAnthropicService:
    """Test cases for AnthropicService."""

    def test_send_prompt_returns_mock_response(self):
        """Test that send_prompt method works with mock provider."""
        mock_provider = Mock()
        mock_provider.send_request.return_value = "Anthropic response"

        service = AnthropicService(provider=mock_provider)
        result = service.send_prompt("Test prompt")

        assert result == "Anthropic response"
        mock_provider.send_request.assert_called_once_with("Test prompt")

    def test_analyze_failure_returns_failure_analysis(self):
        """Test that analyze_failure returns a FailureAnalysis object."""
        mock_provider = Mock()
        mock_provider.send_request.return_value = "Anthropic analysis"

        failure = PytestFailure(
            test_name="test_example",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="Test failed",
            traceback="Traceback here",
        )

        service = AnthropicService(provider=mock_provider)
        result = service.analyze_failure(failure)

        assert isinstance(result, FailureAnalysis)
        assert result.failure == failure
        assert result.root_cause == "Anthropic analysis"
        assert result.error_type == "Anthropic"
        assert result.confidence == 0.8


class TestMockLLMService:
    """Test cases for MockLLMService."""

    def test_send_prompt_returns_mock_response(self):
        """Test that send_prompt returns a consistent mock response."""
        service = MockLLMService()
        result = service.send_prompt("Any prompt")

        assert result == "Mock response"

    def test_analyze_failure_returns_mock_analysis(self):
        """Test that analyze_failure returns a mock FailureAnalysis."""
        failure = PytestFailure(
            test_name="test_example",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="Test failed",
            traceback="Traceback here",
        )

        service = MockLLMService()
        result = service.analyze_failure(failure)

        assert isinstance(result, FailureAnalysis)
        assert result.failure == failure
        assert result.root_cause == "Mock root cause"
        assert result.error_type == "Mock"
        assert result.confidence == 0.5

    def test_suggest_fixes_returns_mock_suggestions(self):
        """Test that suggest_fixes returns mock fix suggestions."""
        failure = PytestFailure(
            test_name="test_example",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="Test failed",
            traceback="Traceback here",
        )

        service = MockLLMService()
        result = service.suggest_fixes(failure)

        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], FixSuggestion)
        assert result[0].failure == failure
        assert result[0].suggestion == "Mock fix suggestion"
        assert result[0].confidence == 0.5

    def test_all_methods_work_without_provider(self):
        """Test that MockLLMService works without a real provider."""
        service = MockLLMService()

        # All methods should work without errors
        prompt_result = service.send_prompt("test")
        assert prompt_result == "Mock response"

        failure = PytestFailure(
            test_name="test_example",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="Test failed",
            traceback="Traceback here",
        )

        analysis = service.analyze_failure(failure)
        assert isinstance(analysis, FailureAnalysis)

        suggestions = service.suggest_fixes(failure, analysis)
        assert isinstance(suggestions, list)
        assert len(suggestions) == 1
