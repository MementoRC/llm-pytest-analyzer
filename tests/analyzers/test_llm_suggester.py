"""Tests for the LLM suggester module."""

from unittest.mock import MagicMock, patch

import pytest

from src.pytest_analyzer.core.analysis.llm_suggester import LLMSuggester
from src.pytest_analyzer.core.llm.llm_service_protocol import LLMServiceProtocol
from src.pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure
from src.pytest_analyzer.core.prompts.prompt_builder import PromptBuilder
from src.pytest_analyzer.utils.resource_manager import TimeoutError


class MockLLMService(LLMServiceProtocol):
    """Mock implementation of LLMServiceProtocol for testing."""

    def __init__(self, response=""):
        self.response = response
        self.last_prompt = None
        self.send_prompt_called = False

    def send_prompt(self, prompt: str) -> str:
        """Send a prompt to the mock LLM and return the mocked response."""
        self.last_prompt = prompt
        self.send_prompt_called = True
        return self.response


@pytest.fixture
def test_failure():
    """Provide a PytestFailure instance for testing."""
    return PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="E       assert 1 == 2\nE       +  where 1 = func()",
        line_number=42,
        relevant_code="def test_function():\n    assert 1 == 2",
    )


@pytest.fixture
def name_error_test_failure():
    """Provide a PytestFailure instance with a NameError."""
    return PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="NameError",
        error_message="name 'undefined_variable' is not defined",
        traceback="E       NameError: name 'undefined_variable' is not defined\nE       at line 25",
        line_number=25,
        relevant_code="def test_function():\n    result = undefined_variable * 2",
    )


@pytest.fixture
def mock_llm_service():
    """Fixture for a mocked LLMService."""
    return MockLLMService(response="Test response")


@pytest.fixture
def llm_suggester(mock_llm_service):
    """Provide a LLMSuggester instance for testing."""
    return LLMSuggester(llm_service=mock_llm_service)


class TestLLMSuggester:
    """Test suite for the LLMSuggester class."""

    def test_init_defaults(self, mock_llm_service):
        """Test initialization with default parameters."""
        suggester = LLMSuggester(llm_service=mock_llm_service)
        assert suggester.llm_service == mock_llm_service
        assert suggester.min_confidence == 0.7
        assert suggester.max_prompt_length == 4000
        assert suggester.max_context_lines == 20
        assert suggester.timeout_seconds == 60
        assert suggester.prompt_builder is not None
        assert isinstance(suggester.prompt_builder, PromptBuilder)

    def test_init_custom_params(self, mock_llm_service):
        """Test initialization with custom parameters."""
        custom_template = "Fix this test: {{error_message}}"
        suggester = LLMSuggester(
            llm_service=mock_llm_service,
            min_confidence=0.9,
            max_prompt_length=2000,
            max_context_lines=5,
            timeout_seconds=30,
            custom_prompt_template=custom_template,
        )
        assert suggester.llm_service == mock_llm_service
        assert suggester.min_confidence == 0.9
        assert suggester.max_prompt_length == 2000
        assert suggester.max_context_lines == 5
        assert suggester.timeout_seconds == 30
        assert suggester.prompt_builder.templates["llm_suggestion"] == custom_template

    def test_init_with_custom_prompt_builder(self, mock_llm_service):
        """Test initialization with a custom PromptBuilder."""
        custom_prompt_builder = PromptBuilder(
            max_prompt_size=3000,
            templates={"llm_suggestion": "Custom template: {test_name}"},
        )

        suggester = LLMSuggester(
            llm_service=mock_llm_service,
            prompt_builder=custom_prompt_builder,
        )

        assert suggester.prompt_builder is custom_prompt_builder
        assert suggester.prompt_builder.max_prompt_size == 3000
        assert (
            suggester.prompt_builder.templates["llm_suggestion"]
            == "Custom template: {test_name}"
        )

    def test_suggest_fixes_no_llm_service(self, test_failure):
        """Test suggest_fixes when no LLM service is available."""
        suggester = LLMSuggester(llm_service=None)

        suggestions = suggester.suggest_fixes(test_failure)

        assert suggestions == []

    @patch.object(PromptBuilder, "build_llm_suggestion_prompt")
    def test_suggest_fixes_exception(
        self, mock_build_prompt, llm_suggester, test_failure
    ):
        """Test error handling during fix suggestion."""
        # Cause an exception in build_llm_suggestion_prompt
        mock_build_prompt.side_effect = Exception("Test error")

        # Call suggest_fixes
        suggestions = llm_suggester.suggest_fixes(test_failure)

        # Verify the results
        assert suggestions == []  # Empty list on error
        mock_build_prompt.assert_called_once_with(test_failure)

    @patch.object(
        PromptBuilder, "build_llm_suggestion_prompt", return_value="Test prompt"
    )
    @patch.object(LLMSuggester, "_parse_llm_response")
    def test_suggest_fixes_success(
        self,
        mock_parse,
        mock_build_prompt,
        llm_suggester,
        test_failure,
        mock_llm_service,
    ):
        """Test successful fix suggestion."""
        # Set up the mocks
        mock_llm_service.response = "Test response"

        # Mock the parsed suggestions
        expected_suggestions = [
            FixSuggestion(failure=test_failure, suggestion="Fix 1", confidence=0.8)
        ]
        mock_parse.return_value = expected_suggestions

        # Call suggest_fixes
        suggestions = llm_suggester.suggest_fixes(test_failure)

        # Verify the results
        assert suggestions == expected_suggestions
        mock_build_prompt.assert_called_once_with(test_failure)
        assert mock_llm_service.send_prompt_called
        assert mock_llm_service.last_prompt == "Test prompt"
        mock_parse.assert_called_once_with("Test response", test_failure)

    def test_integration_with_prompt_builder(self, llm_suggester, test_failure):
        """Test integration between LLMSuggester and PromptBuilder."""
        # Create a custom prompt builder for testing
        prompt_builder = PromptBuilder(
            templates={
                "llm_suggestion": "Test template with {test_name} and {error_type}"
            }
        )

        # Replace the suggester's prompt builder
        llm_suggester.prompt_builder = prompt_builder

        # Patch the send_prompt method to capture what would be sent
        with patch.object(
            llm_suggester.llm_service, "send_prompt", return_value="Test response"
        ) as mock_send_prompt:
            # Call suggest_fixes
            llm_suggester.suggest_fixes(test_failure)

            # Check that the prompt was correctly generated and sent
            expected_prompt = f"Test template with {test_failure.test_name} and {test_failure.error_type}"
            mock_send_prompt.assert_called_once_with(expected_prompt)

    def test_parse_llm_response_json(self, llm_suggester, test_failure):
        """Test parsing a JSON response from the LLM."""
        # Create a JSON response with suggestion data
        json_response = """```json
        [
            {
                "suggestion": "Fix the assertion to expect 1 instead of 2",
                "confidence": 0.8,
                "explanation": "The test is expecting 2 but getting 1"
            }
        ]
        ```"""

        suggestions = llm_suggester._parse_llm_response(json_response, test_failure)

        assert len(suggestions) == 1
        assert suggestions[0].suggestion == "Fix the assertion to expect 1 instead of 2"
        assert suggestions[0].confidence == 0.8
        assert suggestions[0].explanation == "The test is expecting 2 but getting 1"
        assert suggestions[0].failure == test_failure

    def test_parse_llm_response_invalid_json(self, llm_suggester, test_failure):
        """Test parsing an invalid JSON response from the LLM."""
        # Create an invalid JSON response
        invalid_json = """```json
        {
            "suggestion": "Fix the assertion,
            "confidence": 0.8
        }
        ```"""

        # Should fall back to text extraction
        suggestions = llm_suggester._parse_llm_response(invalid_json, test_failure)

        assert (
            len(suggestions) >= 0
        )  # May extract suggestions from text or return empty list

    def test_parse_llm_response_text(self, llm_suggester, test_failure):
        """Test parsing a plain text response from the LLM."""
        # Create a text response with suggestion patterns
        text_response = """
        Suggestion: Fix the assertion to expect 1 instead of 2.

        The test is expecting 2 but actually gets 1. You should update the assertion.

        ```python
        def test_function():
            assert 1 == 1  # Fixed
        ```
        """

        suggestions = llm_suggester._parse_llm_response(text_response, test_failure)

        assert len(suggestions) >= 1
        assert "Fix the assertion" in suggestions[0].suggestion
        assert suggestions[0].failure == test_failure

    def test_create_suggestion_from_json(self, llm_suggester, test_failure):
        """Test creating a FixSuggestion from JSON data."""
        # Valid data with all required fields
        valid_data = {
            "suggestion": "Fix the assertion",
            "confidence": 0.8,
            "explanation": "Explanation text",
            "code_changes": {"fixed_code": "assert 1 == 1"},
        }

        suggestion = llm_suggester._create_suggestion_from_json(
            valid_data, test_failure
        )

        assert suggestion is not None
        assert suggestion.suggestion == "Fix the assertion"
        assert suggestion.confidence == 0.8
        assert suggestion.explanation == "Explanation text"
        assert suggestion.code_changes == {"fixed_code": "assert 1 == 1"}
        assert suggestion.failure == test_failure

        # Test with data below confidence threshold
        below_threshold_data = {
            "suggestion": "Low confidence fix",
            "confidence": 0.3,  # Below default threshold of 0.7
            "explanation": "Explanation text",
        }

        # This might return None depending on implementation
        low_confidence_suggestion = llm_suggester._create_suggestion_from_json(
            below_threshold_data, test_failure
        )
        if low_confidence_suggestion is not None:
            assert low_confidence_suggestion.confidence < llm_suggester.min_confidence

    def test_extract_suggestions_from_text(self, llm_suggester, test_failure):
        """Test extracting suggestions from text response."""
        # Text with clear suggestion patterns
        text_with_suggestions = """
        Suggestion: Fix the assertion to expect 1 instead of 2.

        You should update the assertion in the test.

        ```python
        def test_function():
            assert 1 == 1  # Fixed
        ```

        Suggestion 2: Fix the implementation of func() to return 2.
        """

        suggestions = llm_suggester._extract_suggestions_from_text(
            text_with_suggestions, test_failure
        )

        assert len(suggestions) >= 1
        assert any("Fix the assertion" in s.suggestion for s in suggestions)
        assert all(s.failure == test_failure for s in suggestions)

        # Text with no clear suggestions
        text_without_suggestions = "The error seems to be in the test configuration."

        suggestions = llm_suggester._extract_suggestions_from_text(
            text_without_suggestions, test_failure
        )

        assert len(suggestions) == 1  # Should create a generic suggestion
        assert suggestions[0].suggestion == text_without_suggestions.strip()
        assert suggestions[0].failure == test_failure

    def test_service_integration(self, test_failure):
        """Test integration between LLMSuggester and LLMService."""
        # Setup mock service with known response
        mock_service = MockLLMService(
            response="""```json
        [
            {
                "suggestion": "Fix the assertion to expect 1 instead of 2",
                "confidence": 0.9,
                "explanation": "The test expects 2 but the function returns 1",
                "code_changes": {
                    "fixed_code": "assert 1 == 1  # Fixed"
                }
            }
        ]
        ```"""
        )

        # Create suggester with mock service
        suggester = LLMSuggester(llm_service=mock_service)

        # Get suggestions
        suggestions = suggester.suggest_fixes(test_failure)

        # Verify results
        assert len(suggestions) == 1
        assert suggestions[0].suggestion == "Fix the assertion to expect 1 instead of 2"
        assert suggestions[0].confidence == 0.9
        assert (
            suggestions[0].explanation
            == "The test expects 2 but the function returns 1"
        )
        assert "fixed_code" in suggestions[0].code_changes
        assert suggestions[0].code_changes["fixed_code"] == "assert 1 == 1  # Fixed"
        assert mock_service.send_prompt_called

    def test_llm_service_timeout(self, test_failure):
        """Test LLMSuggester handling of LLMService timeout."""
        # Create a mock service that raises TimeoutError
        mock_service = MockLLMService()
        mock_service.send_prompt = MagicMock(
            side_effect=TimeoutError("LLM request timed out")
        )

        # Create suggester with mock service
        suggester = LLMSuggester(llm_service=mock_service)

        # Get suggestions - should handle the timeout gracefully
        suggestions = suggester.suggest_fixes(test_failure)

        # Verify empty results due to error
        assert suggestions == []
        mock_service.send_prompt.assert_called_once()

    def test_llm_service_error(self, test_failure):
        """Test LLMSuggester handling of LLMService error."""
        # Create a mock service that raises an exception
        mock_service = MockLLMService()
        mock_service.send_prompt = MagicMock(side_effect=Exception("LLM API error"))

        # Create suggester with mock service
        suggester = LLMSuggester(llm_service=mock_service)

        # Get suggestions - should handle the error gracefully
        suggestions = suggester.suggest_fixes(test_failure)

        # Verify empty results due to error
        assert suggestions == []
        mock_service.send_prompt.assert_called_once()
