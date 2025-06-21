"""Tests for the fix suggester module."""

from unittest.mock import patch

import pytest

from pytest_analyzer.core.analysis.fix_suggester import FixSuggester
from pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure


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
def fix_suggester():
    """Provide a FixSuggester instance for testing."""
    return FixSuggester()


@patch("pytest_analyzer.core.analysis.fix_suggester.AssertionErrorStrategy.analyze")
def test_suggest_fixes(mock_analyze, fix_suggester, test_failure):
    """Test suggesting fixes for a test failure."""
    # Mock the analyze method to return a known result
    mock_analyze.return_value = [
        FixSuggestion(failure=test_failure, suggestion="Fix 1", confidence=0.8),
        FixSuggestion(failure=test_failure, suggestion="Fix 2", confidence=0.6),
        FixSuggestion(failure=test_failure, suggestion="Fix 3", confidence=0.4),
    ]

    # Suggest fixes
    suggestions = fix_suggester.suggest_fixes(test_failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert (
        len(suggestions) == 2
    )  # Only suggestions with confidence >= 0.5 should be returned
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)
    assert all(suggestion.confidence >= 0.5 for suggestion in suggestions)


@patch("pytest_analyzer.core.analysis.fix_suggester.AssertionErrorStrategy.analyze")
def test_suggest_fixes_min_confidence(mock_analyze, test_failure):
    """Test minimum confidence filtering."""
    # Create a FixSuggester with a custom min_confidence
    suggester = FixSuggester(min_confidence=0.7)

    # Mock the analyze method to return a known result
    mock_analyze.return_value = [
        FixSuggestion(failure=test_failure, suggestion="Fix 1", confidence=0.8),
        FixSuggestion(failure=test_failure, suggestion="Fix 2", confidence=0.6),
        FixSuggestion(failure=test_failure, suggestion="Fix 3", confidence=0.4),
    ]

    # Suggest fixes
    suggestions = suggester.suggest_fixes(test_failure)

    # Verify the results
    assert (
        len(suggestions) == 1
    )  # Only suggestions with confidence >= 0.7 should be returned
    assert suggestions[0].suggestion == "Fix 1"


@patch("logging.Logger.error")
@patch("pytest_analyzer.core.analysis.fix_suggester.AssertionErrorStrategy.analyze")
def test_suggest_fixes_exception(
    mock_analyze, mock_logger_error, fix_suggester, test_failure
):
    """Test error handling during fix suggestion."""
    # Mock the analyze method to raise an exception
    mock_analyze.side_effect = Exception("Test error")

    # Suggest fixes
    suggestions = fix_suggester.suggest_fixes(test_failure)

    # Verify the results
    assert suggestions == []  # Empty list on error
    mock_logger_error.assert_called_once()


@patch("pytest_analyzer.core.analysis.fix_suggester.GenericErrorStrategy.analyze")
def test_suggest_fixes_handles_unknown_error_types(mock_analyze, fix_suggester):
    """Test that an unknown error type falls back to the generic strategy."""
    unknown_failure = PytestFailure(
        test_name="test.py::test_func",
        test_file="test.py",
        error_type="UnknownError",
        error_message="Sample unknown error",
        traceback="E       UnknownError: Sample unknown error",
    )
    mock_analyze.return_value = []

    fix_suggester.suggest_fixes(unknown_failure)

    mock_analyze.assert_called_once_with(unknown_failure)


@pytest.mark.parametrize(
    "error_type, strategy_name",
    [
        ("AssertionError", "AssertionErrorStrategy"),
        ("AttributeError", "AttributeErrorStrategy"),
        ("ImportError", "ImportErrorStrategy"),
        ("TypeError", "TypeErrorStrategy"),
        ("NameError", "NameErrorStrategy"),
        ("IndexError", "IndexErrorStrategy"),
        ("KeyError", "KeyErrorStrategy"),
        ("ValueError", "ValueErrorStrategy"),
        ("SyntaxError", "SyntaxErrorStrategy"),
    ],
)
def test_suggest_fixes_delegates_to_correct_strategy(
    error_type, strategy_name, fix_suggester
):
    """Test that suggest_fixes delegates to the correct strategy for each error type."""
    failure = PytestFailure(
        test_name="test.py::test_func",
        test_file="test.py",
        error_type=error_type,
        error_message=f"Sample {error_type}",
        traceback=f"E       {error_type}: Sample {error_type}",
    )

    strategy_path = (
        f"pytest_analyzer.core.analysis.fix_suggester.{strategy_name}.analyze"
    )
    with patch(strategy_path) as mock_analyze:
        mock_analyze.return_value = []
        fix_suggester.suggest_fixes(failure)
        mock_analyze.assert_called_once_with(failure)
