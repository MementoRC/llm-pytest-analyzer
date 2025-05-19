"""
Tests for the ResponseParser component.
"""

import pytest

from src.pytest_analyzer.core.errors import ParsingError
from src.pytest_analyzer.core.models.failure_analysis import FailureAnalysis
from src.pytest_analyzer.core.models.pytest_failure import PytestFailure
from src.pytest_analyzer.core.parsers.response_parser import ResponseParser


@pytest.fixture
def test_failure():
    """Create a sample test failure for testing."""
    return PytestFailure(
        test_name="test_addition",
        test_file="test_math.py",
        error_type="AssertionError",
        error_message="assert 1 + 1 == 3",
        traceback="Traceback...\nE   AssertionError: assert 1 + 1 == 3",
        line_number=42,
        relevant_code="def test_addition():\n    assert 1 + 1 == 3",
    )


@pytest.fixture
def test_analysis(test_failure):
    """Create a sample failure analysis for testing."""
    return FailureAnalysis(
        failure=test_failure,
        root_cause="Incorrect expected value in assertion",
        error_type="AssertionError",
        suggested_fixes=["Change expected value from 3 to 2"],
        confidence=0.9,
    )


class TestResponseParser:
    """Tests for the ResponseParser class."""

    def test_parse_analysis_response_with_structured_content(self, test_failure):
        """Test parsing a well-structured analysis response."""
        response = """
        Based on the test failure, here's my analysis:

        Root Cause: Incorrect expected value in the assertion
        Error Type: AssertionError

        Fixes:
        - Change the assertion to expect 2 instead of 3
        - Modify the addition function to return 3 when given 1 + 1

        I'm confident this is the issue.
        """

        analysis = ResponseParser.parse_analysis_response(test_failure, response)

        assert analysis.failure == test_failure
        assert "Incorrect expected value" in analysis.root_cause
        assert analysis.error_type == "AssertionError"
        assert len(analysis.suggested_fixes) == 2
        assert "Change the assertion" in analysis.suggested_fixes[0]
        assert "Modify the addition function" in analysis.suggested_fixes[1]
        assert analysis.confidence > 0.8  # Should have high confidence

    def test_parse_analysis_response_with_unstructured_content(self, test_failure):
        """Test parsing an unstructured analysis response."""
        response = """
        The test is failing because it expects 1 + 1 to equal 3, but it actually equals 2.
        You should change the assertion to expect 2 instead of 3.
        """

        analysis = ResponseParser.parse_analysis_response(test_failure, response)

        assert analysis.failure == test_failure
        assert analysis.root_cause == "Unknown"  # No explicit root cause
        assert analysis.error_type == "Unknown"  # No explicit error type
        assert analysis.confidence == 0.7  # Default confidence

    def test_parse_analysis_response_with_explicit_confidence(self, test_failure):
        """Test parsing a response with explicit confidence information."""
        response = """
        Root Cause: Incorrect expected value
        Error Type: AssertionError

        Confidence: 95%

        I'm certain this is the issue.
        """

        analysis = ResponseParser.parse_analysis_response(test_failure, response)

        assert analysis.confidence == 0.95  # Parsed from the explicit mention

    def test_parse_analysis_response_with_empty_content(self, test_failure):
        """Test parsing an empty response."""
        response = ""

        analysis = ResponseParser.parse_analysis_response(test_failure, response)

        assert analysis.root_cause == "Unknown"
        assert analysis.error_type == "Unknown"
        assert len(analysis.suggested_fixes) == 0
        assert analysis.confidence == 0.7  # Default confidence

    def test_parse_analysis_response_exception_handling(
        self, test_failure, monkeypatch
    ):
        """Test exception handling when parsing fails."""

        # Mock re.search to raise an exception
        def mock_search(*args, **kwargs):
            raise ValueError("Simulated failure in regex search")

        monkeypatch.setattr("re.search", mock_search)

        with pytest.raises(ParsingError):
            ResponseParser.parse_analysis_response(test_failure, "Some response")

    def test_parse_suggestion_response_with_json_format(
        self, test_failure, test_analysis
    ):
        """Test parsing a suggestion response in JSON format."""
        response = """
        Here's how to fix the problem:

        ```json
        [
          {
            "suggestion": "Change the assertion to expect 2 instead of 3",
            "confidence": 0.9,
            "explanation": "The test expects 1 + 1 to equal 3, but it's actually 2",
            "code_changes": {
              "file": "test_math.py",
              "original_code": "assert 1 + 1 == 3",
              "fixed_code": "assert 1 + 1 == 2"
            }
          }
        ]
        ```
        """

        suggestions = ResponseParser.parse_suggestion_response(
            test_failure, test_analysis, response
        )

        assert len(suggestions) == 1
        suggestion = suggestions[0]
        assert suggestion.failure == test_failure
        assert "Change the assertion" in suggestion.suggestion
        assert suggestion.confidence == 0.9
        assert "original_code" in suggestion.code_changes
        assert suggestion.code_changes["fixed_code"] == "assert 1 + 1 == 2"

    def test_parse_suggestion_response_with_malformed_json(
        self, test_failure, test_analysis
    ):
        """Test parsing a suggestion response with malformed JSON."""
        response = """
        Here's how to fix the problem:

        ```json
        {
          "suggestion": "Change the assertion to expect 2 instead of 3",
          "confidence": 0.9,
          "explanation": "The test expects 1 + 1 to equal 3, but it's actually 2",
          "code_changes":  // Missing closing brace
        ```

        Hope this helps!
        """

        suggestions = ResponseParser.parse_suggestion_response(
            test_failure, test_analysis, response
        )

        # Should extract from text since JSON is malformed
        assert len(suggestions) == 1
        assert suggestions[0].confidence == 0.7  # Default confidence
        assert "source" in suggestions[0].code_changes
        assert suggestions[0].code_changes["source"] == "llm"

    def test_parse_suggestion_response_with_code_blocks(
        self, test_failure, test_analysis
    ):
        """Test parsing a suggestion with Python code blocks."""
        response = """
        Suggestion: Update the test in test_math.py to expect the correct result

        ```python
        def test_addition():
            # 1 + 1 = 2, not 3
            assert 1 + 1 == 2
        ```

        This should fix the issue.
        """

        suggestions = ResponseParser.parse_suggestion_response(
            test_failure, test_analysis, response
        )

        assert len(suggestions) == 1
        suggestion = suggestions[0]
        assert "Update the test" in suggestion.suggestion
        assert "code_snippet_1" in suggestion.code_changes
        assert "def test_addition():" in suggestion.code_changes["code_snippet_1"]

    def test_parse_suggestion_response_with_multiple_suggestions(
        self, test_failure, test_analysis
    ):
        """Test parsing a response with multiple suggestions."""
        response = """
        Suggestion 1: Update the test expectation

        ```python
        def test_addition():
            assert 1 + 1 == 2  # Changed from 3 to 2
        ```

        Suggestion 2: Change the implementation to match the test

        ```python
        def add(a, b):
            # Make 1 + 1 = 3 as the test expects
            if a == 1 and b == 1:
                return 3
            return a + b
        ```
        """

        suggestions = ResponseParser.parse_suggestion_response(
            test_failure, test_analysis, response
        )

        assert len(suggestions) == 2
        assert "Update the test expectation" in suggestions[0].suggestion
        assert "Change the implementation" in suggestions[1].suggestion

    def test_parse_suggestion_response_exception_handling(
        self, test_failure, test_analysis, monkeypatch
    ):
        """Test exception handling when parsing fails."""

        # Mock re.findall to raise an exception
        def mock_findall(*args, **kwargs):
            raise ValueError("Simulated failure in regex findall")

        monkeypatch.setattr("re.findall", mock_findall)

        with pytest.raises(ParsingError):
            ResponseParser.parse_suggestion_response(
                test_failure, test_analysis, "Some response"
            )
