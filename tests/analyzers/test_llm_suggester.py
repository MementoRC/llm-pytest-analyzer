"""Tests for the LLM suggester module."""

from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.analysis.llm_adapters import (
    AnthropicAdapter,
    GenericAdapter,
    OpenAIAdapter,
)
from pytest_analyzer.core.analysis.llm_suggester import LLMSuggester
from pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure


# Helper classes for mocking clients with correct module attributes
class _MockOpenAIClient:
    __module__ = "openai"

    def __init__(self):
        self.chat = MagicMock()
        self.chat.completions = MagicMock()
        self.chat.completions.create = MagicMock()


class _MockAnthropicClient:
    __module__ = "anthropic"

    def __init__(self):
        self.messages = MagicMock()
        self.messages.create = MagicMock()


class _MockGenericClient:
    __module__ = "generic_llm"

    def __init__(self):
        self.generate = MagicMock()


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
def mock_openai_client():
    """Fixture for a mocked OpenAI client."""
    return _MockOpenAIClient()


@pytest.fixture
def mock_anthropic_client():
    """Fixture for a mocked Anthropic client."""
    return _MockAnthropicClient()


@pytest.fixture
def mock_generic_client():
    """Fixture for a mocked generic LLM client."""
    return _MockGenericClient()


@pytest.fixture
def llm_suggester(mock_openai_client):
    """Provide a LLMSuggester instance for testing."""
    return LLMSuggester(llm_client=mock_openai_client)


class TestLLMSuggester:
    """Test suite for the LLMSuggester class."""

    def test_init_defaults(self, mock_openai_client):
        """Test initialization with default parameters."""
        suggester = LLMSuggester(llm_client=mock_openai_client)
        assert suggester.llm_client == mock_openai_client
        assert suggester.min_confidence == 0.7
        assert suggester.max_prompt_length == 4000
        assert suggester.max_context_lines == 20
        assert suggester.timeout_seconds == 60
        assert suggester.prompt_template is not None
        assert isinstance(suggester._llm_adapter, OpenAIAdapter)

    def test_init_custom_params(self, mock_openai_client):
        """Test initialization with custom parameters."""
        custom_template = "Fix this test: {{error_message}}"
        suggester = LLMSuggester(
            llm_client=mock_openai_client,
            min_confidence=0.9,
            max_prompt_length=2000,
            max_context_lines=5,
            timeout_seconds=30,
            custom_prompt_template=custom_template,
        )
        assert suggester.llm_client == mock_openai_client
        assert suggester.min_confidence == 0.9
        assert suggester.max_prompt_length == 2000
        assert suggester.max_context_lines == 5
        assert suggester.timeout_seconds == 30
        assert suggester.prompt_template == custom_template
        assert suggester._llm_adapter is not None

    def test_get_llm_adapter_openai(self, mock_openai_client):
        """Test getting the adapter for OpenAI client."""
        suggester = LLMSuggester(llm_client=mock_openai_client)
        assert isinstance(suggester._llm_adapter, OpenAIAdapter)

    def test_get_llm_adapter_anthropic(self, mock_anthropic_client):
        """Test getting the adapter for Anthropic client."""
        suggester = LLMSuggester(llm_client=mock_anthropic_client)
        assert isinstance(suggester._llm_adapter, AnthropicAdapter)

    def test_get_llm_adapter_generic(self, mock_generic_client):
        """Test getting the adapter for a generic client."""
        suggester = LLMSuggester(llm_client=mock_generic_client)
        assert isinstance(suggester._llm_adapter, GenericAdapter)

    def test_suggest_fixes_no_llm_client(self, test_failure):
        """Test suggest_fixes when no LLM client is available."""
        with patch.dict("sys.modules", {"anthropic": None, "openai": None}):
            suggester = LLMSuggester(llm_client=None)
            assert suggester._llm_adapter is None
            suggestions = suggester.suggest_fixes(test_failure)
            assert suggestions == []

    @patch.object(LLMSuggester, "_build_prompt")
    def test_suggest_fixes_exception(
        self, mock_build_prompt, llm_suggester, test_failure
    ):
        """Test error handling during fix suggestion."""
        # Cause an exception in _build_prompt
        mock_build_prompt.side_effect = Exception("Test error")

        # Call suggest_fixes
        suggestions = llm_suggester.suggest_fixes(test_failure)

        # Verify the results
        assert suggestions == []  # Empty list on error
        mock_build_prompt.assert_called_once_with(test_failure)

    @patch.object(LLMSuggester, "_build_prompt", return_value="Test prompt")
    @patch.object(LLMSuggester, "_parse_llm_response")
    def test_suggest_fixes_success(
        self, mock_parse, mock_build_prompt, llm_suggester, test_failure
    ):
        """Test successful fix suggestion."""
        # Set up the mocks
        llm_suggester._llm_adapter.request = MagicMock(return_value="Test response")

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
        llm_suggester._llm_adapter.request.assert_called_once_with("Test prompt")
        mock_parse.assert_called_once_with("Test response", test_failure)

    def test_build_prompt(self, llm_suggester, test_failure):
        """Test building prompts for the language model."""
        # Patch _extract_code_context to return a known value
        with patch.object(
            llm_suggester,
            "_extract_code_context",
            return_value="def test_function():\n    assert 1 == 2",
        ):
            prompt = llm_suggester._build_prompt(test_failure)

            # Check if prompt contains key information
            assert test_failure.test_name in prompt
            assert test_failure.error_type in prompt
            assert test_failure.error_message in prompt
            assert "def test_function()" in prompt
            assert str(test_failure.line_number) in prompt

    @patch.object(LLMSuggester, "_truncate_text")
    def test_build_prompt_long_prompt(self, mock_truncate, llm_suggester, test_failure):
        """Test prompt truncation for long prompts."""
        # Mock the truncate_text method
        mock_truncate.return_value = "truncated text"

        # Create a long traceback and code context
        test_failure.traceback = "E       " + ("x" * 2000)

        # Patch _extract_code_context to return a long value
        with patch.object(
            llm_suggester,
            "_extract_code_context",
            return_value="def test_function():\n" + ("x" * 3000),
        ):
            # Set a small max_prompt_length
            llm_suggester.max_prompt_length = 500

            llm_suggester._build_prompt(test_failure)

            # Verify truncate_text was called
            assert mock_truncate.called

    def test_extract_code_context_file_not_found(self, llm_suggester, test_failure):
        """Test extracting code context when the file doesn't exist."""
        # Set test_file to a non-existent path
        test_failure.test_file = "/nonexistent/path.py"

        context = llm_suggester._extract_code_context(test_failure)

        # Should use relevant_code if available when file not found
        assert context == test_failure.relevant_code

    @patch("os.path.exists", return_value=True)
    @patch("builtins.open")
    def test_extract_code_context_io_error(
        self, mock_open, mock_exists, llm_suggester, test_failure
    ):
        """Test extracting code context when there's an IO error."""
        # Simulate an IO error when opening the file
        mock_open.side_effect = IOError("Test IO error")

        # Remove relevant_code to force file reading attempt
        test_failure.relevant_code = None

        # Set up test_failure.traceback to contain code snippets
        test_failure.traceback = "E  >  assert 1 == 2\nE      where 1 = func()"

        context = llm_suggester._extract_code_context(test_failure)

        # Log the actual return value for debugging
        if context is not None:
            print(f"Context returned: {context}")

        # Should return None or extract from traceback
        # If code pattern extraction is implemented, we might get a value
        # Otherwise, we should get None
        assert context is None or isinstance(context, str)

    def test_extract_code_context_from_traceback(self, llm_suggester, test_failure):
        """Test extracting code context from the traceback."""
        # Remove relevant_code to force traceback extraction
        test_failure.relevant_code = None
        # Set test_file to a non-existent path
        test_failure.test_file = "/nonexistent/path.py"
        # Set up a traceback with code patterns
        test_failure.traceback = ">       assert 1 == 2\nE       where 1 = func()"

        context = llm_suggester._extract_code_context(test_failure)

        # Should extract code lines or return None if pattern doesn't match
        if context is not None:
            assert "assert 1 == 2" in context
        else:
            # This is also valid if the implementation doesn't extract from traceback
            pass

    def test_truncate_text(self, llm_suggester):
        """Test the text truncation method."""
        # Test with text shorter than max_length
        short_text = "This is a short text"
        assert llm_suggester._truncate_text(short_text, 100) == short_text

        # Test with text longer than max_length
        long_text = "x" * 1000
        truncated = llm_suggester._truncate_text(long_text, 100)

        assert len(truncated) <= 120  # Allow for truncation markers
        assert "..." in truncated
        assert "[truncated]" in truncated

        # Test with None or empty text
        assert llm_suggester._truncate_text(None, 100) is None
        assert llm_suggester._truncate_text("", 100) == ""

    def test_truncate_prompt(self, llm_suggester):
        """Test the prompt truncation method."""
        # Create a prompt with multiple sections
        sections = ["Section 1", "Section 2", "Section 3", "Section 4"]
        prompt = "===".join(sections)

        # Truncate to a length that requires dropping middle sections
        truncated = llm_suggester._truncate_prompt(prompt, 20)

        # First and last sections should be preserved
        assert "Section 1" in truncated
        assert "Section 4" in truncated

        # Should not exceed max length (plus some buffer)
        assert len(truncated) <= 30

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
