"""
Tests for the refactored LLMService implementation.
"""

from unittest.mock import MagicMock

import pytest

from pytest_analyzer.core.errors import LLMServiceError, ParsingError
from pytest_analyzer.core.llm.llm_service import LLMService
from pytest_analyzer.core.models.failure_analysis import FailureAnalysis
from pytest_analyzer.core.models.pytest_failure import PytestFailure
from pytest_analyzer.core.parsers.response_parser import ResponseParser
from pytest_analyzer.core.prompts.prompt_builder import PromptBuilder
from pytest_analyzer.utils.resource_manager import (
    ResourceMonitor,
)
from pytest_analyzer.utils.resource_manager import TimeoutError as ResourceManagerTimeoutError


# Sample test data
@pytest.fixture
def sample_failure():
    """Sample pytest failure for testing."""
    return PytestFailure(
        test_name="test_example",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback='Traceback (most recent call last):\n  File "test_file.py", line 42\n    assert 1 == 2',
        line_number=42,
        relevant_code="def test_example():\n    assert 1 == 2",
    )


@pytest.fixture
def sample_analysis(sample_failure):
    """Sample failure analysis for testing."""
    return FailureAnalysis(
        failure=sample_failure,
        root_cause="Comparison between different values",
        error_type="AssertionError",
        suggested_fixes=["Change the assertion to use equal values"],
        confidence=0.9,
    )


class TestRefactoredLLMService:
    """Tests for the refactored LLMService implementation."""

    @pytest.fixture
    def mock_prompt_builder(self):
        """Create a mock PromptBuilder for testing."""
        mock = MagicMock(spec=PromptBuilder)
        mock.build_analysis_prompt.return_value = "Analysis prompt for test"
        mock.build_suggestion_prompt.return_value = "Suggestion prompt for test"
        return mock

    @pytest.fixture
    def mock_response_parser(self, sample_failure, sample_analysis):
        """Create a mock ResponseParser for testing."""
        mock = MagicMock(spec=ResponseParser)
        mock.parse_analysis_response.return_value = sample_analysis
        mock.parse_suggestion_response.return_value = [
            {
                "suggestion": "Fix suggestion",
                "confidence": 0.8,
                "code_changes": {"file": "test_file.py", "line": 42},
            }
        ]
        return mock

    @pytest.fixture
    def mock_resource_monitor(self):
        """Create a mock ResourceMonitor for testing."""
        return MagicMock(spec=ResourceMonitor)

    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client for testing."""
        mock = MagicMock()
        mock.__class__.__module__ = "anthropic"

        # Set up the client to return a response
        mock_response = MagicMock()
        mock_message = MagicMock()
        mock_message.text = "Test LLM response"
        mock_response.content = [mock_message]
        mock.messages.create.return_value = mock_response

        return mock

    def test_init_with_dependencies(
        self,
        mock_prompt_builder,
        mock_response_parser,
        mock_resource_monitor,
        mock_llm_client,
    ):
        """Test initializing the service with dependencies."""
        service = LLMService(
            prompt_builder=mock_prompt_builder,
            response_parser=mock_response_parser,
            resource_monitor=mock_resource_monitor,
            llm_client=mock_llm_client,
            timeout_seconds=30,
            max_tokens=2000,
            model_name={"anthropic": "claude-3-sonnet"},
        )

        assert service.prompt_builder is mock_prompt_builder
        assert service.response_parser is mock_response_parser
        assert service.resource_monitor is mock_resource_monitor
        assert service.llm_client is mock_llm_client
        assert service.timeout_seconds == 30
        assert service.max_tokens == 2000
        assert service.model_name["anthropic"] == "claude-3-sonnet"
        assert service._llm_request_func is not None

    def test_analyze_failure(
        self, mock_prompt_builder, mock_response_parser, mock_llm_client, sample_failure
    ):
        """Test analyzing a test failure."""
        # Create a service with mocked dependencies
        service = LLMService(
            prompt_builder=mock_prompt_builder,
            response_parser=mock_response_parser,
            llm_client=mock_llm_client,
        )

        # Set up the mocks for this test
        mock_prompt_builder.build_analysis_prompt.return_value = "Analysis prompt"
        mock_llm_client.messages.create.return_value.content[0].text = "Analysis response"

        # Call the method
        result = service.analyze_failure(sample_failure)

        # Verify the method behavior
        mock_prompt_builder.build_analysis_prompt.assert_called_once_with(sample_failure)
        mock_response_parser.parse_analysis_response.assert_called_once_with(
            sample_failure, "Analysis response"
        )
        assert result == mock_response_parser.parse_analysis_response.return_value

    def test_suggest_fixes(
        self,
        mock_prompt_builder,
        mock_response_parser,
        mock_llm_client,
        sample_failure,
        sample_analysis,
    ):
        """Test suggesting fixes for a test failure."""
        # Create a service with mocked dependencies
        service = LLMService(
            prompt_builder=mock_prompt_builder,
            response_parser=mock_response_parser,
            llm_client=mock_llm_client,
        )

        # Set up the mocks for this test
        mock_prompt_builder.build_suggestion_prompt.return_value = "Suggestion prompt"
        mock_llm_client.messages.create.return_value.content[0].text = "Suggestion response"

        # Call the method with an existing analysis
        result = service.suggest_fixes(sample_failure, sample_analysis)

        # Verify the method behavior
        mock_prompt_builder.build_suggestion_prompt.assert_called_once_with(
            sample_failure, root_cause=sample_analysis.root_cause
        )
        mock_response_parser.parse_suggestion_response.assert_called_once_with(
            sample_failure, sample_analysis, "Suggestion response"
        )
        assert result == mock_response_parser.parse_suggestion_response.return_value

    def test_suggest_fixes_auto_analyze(
        self,
        mock_prompt_builder,
        mock_response_parser,
        mock_llm_client,
        sample_failure,
        sample_analysis,
    ):
        """Test suggesting fixes without an existing analysis."""
        # Create a service with mocked dependencies
        service = LLMService(
            prompt_builder=mock_prompt_builder,
            response_parser=mock_response_parser,
            llm_client=mock_llm_client,
        )

        # Set up the mocks for this test
        mock_prompt_builder.build_analysis_prompt.return_value = "Analysis prompt"
        mock_prompt_builder.build_suggestion_prompt.return_value = "Suggestion prompt"

        # Mock the send_prompt method to return different responses for analysis and suggestion
        service.send_prompt = MagicMock(side_effect=["Analysis response", "Suggestion response"])

        # Set up the response parser to return an analysis and suggestions
        mock_response_parser.parse_analysis_response.return_value = sample_analysis

        # Call the method without an existing analysis (should auto-generate one)
        result = service.suggest_fixes(sample_failure)

        # Verify the method behavior
        assert service.send_prompt.call_count == 2
        mock_prompt_builder.build_analysis_prompt.assert_called_once_with(sample_failure)
        mock_prompt_builder.build_suggestion_prompt.assert_called_once_with(
            sample_failure, root_cause=sample_analysis.root_cause
        )
        mock_response_parser.parse_analysis_response.assert_called_once_with(
            sample_failure, "Analysis response"
        )
        mock_response_parser.parse_suggestion_response.assert_called_once_with(
            sample_failure, sample_analysis, "Suggestion response"
        )
        assert result == mock_response_parser.parse_suggestion_response.return_value

    def test_error_handling_in_send_prompt(self, mock_prompt_builder, mock_response_parser):
        """Test error handling in the send_prompt method."""
        # Create a mock client that raises an exception
        mock_client = MagicMock()
        mock_client.__class__.__module__ = "anthropic"
        mock_client.messages.create.side_effect = Exception("API Error")

        # Create the service
        service = LLMService(
            prompt_builder=mock_prompt_builder,
            response_parser=mock_response_parser,
            llm_client=mock_client,
        )

        # Call send_prompt and expect an exception
        with pytest.raises(LLMServiceError) as exc_info:
            service.send_prompt("Test prompt")

        # Verify the exception details
        assert "Failed to send prompt to language model" in str(exc_info.value)
        assert "API Error" in str(exc_info.value)

    def test_error_handling_in_analyze_failure(
        self, mock_prompt_builder, mock_response_parser, mock_llm_client, sample_failure
    ):
        """Test error handling in the analyze_failure method."""
        # Create the service
        service = LLMService(
            prompt_builder=mock_prompt_builder,
            response_parser=mock_response_parser,
            llm_client=mock_llm_client,
        )

        # Set up the response for send_prompt
        service.send_prompt = MagicMock(return_value="Test LLM response")

        # Make the response parser raise an exception
        mock_response_parser.parse_analysis_response.side_effect = Exception("Parsing Error")

        # Call analyze_failure and expect an exception
        with pytest.raises(ParsingError) as exc_info:
            service.analyze_failure(sample_failure)

        # Verify the exception details
        assert "Failed to parse analysis response" in str(exc_info.value)
        assert "Parsing Error" in str(exc_info.value)

    def test_timeout_handling(
        self, mock_prompt_builder, mock_response_parser, mock_llm_client, sample_failure
    ):
        """Test handling of timeout errors."""
        # Create the service with a very short timeout
        service = LLMService(
            prompt_builder=mock_prompt_builder,
            response_parser=mock_response_parser,
            llm_client=mock_llm_client,
            timeout_seconds=0.1,
        )

        # Override the _request_with_anthropic method to simulate a timeout
        # by raising a TimeoutError directly from resource_manager
        mock_llm_client.messages.create.side_effect = ResourceManagerTimeoutError(
            "Operation timed out"
        )

        # Make sure the service uses our mocked client
        service._llm_request_func = service._request_with_anthropic

        # Call send_prompt and expect a timeout exception
        with pytest.raises(LLMServiceError) as exc_info:
            service.send_prompt("Test prompt")

        # Verify the exception details
        assert "Timeout" in str(exc_info.value)

    def test_error_context_manager(self):
        """Test the error_context context manager."""
        from pytest_analyzer.core.llm.llm_service import error_context

        # Test normal operation
        with error_context(ValueError, "Test error"):
            pass  # No exception raised

        # Test with a regular exception
        with pytest.raises(ValueError) as exc_info:
            with error_context(ValueError, "Test error"):
                raise Exception("Inner error")

        assert "Test error" in str(exc_info.value)
        assert "Inner error" in str(exc_info.value)

        # Test with a timeout exception
        with pytest.raises(ValueError) as exc_info:
            with error_context(ValueError, "Test error"):
                raise ResourceManagerTimeoutError("Timeout occurred")

        assert "Test error" in str(exc_info.value)
        assert "Timeout" in str(exc_info.value)
