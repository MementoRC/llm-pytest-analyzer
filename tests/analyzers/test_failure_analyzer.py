"""Tests for the failure analyzer module."""
import pytest
import re
from unittest.mock import patch, MagicMock

from ...core.analysis.failure_analyzer import FailureAnalyzer
from ...core.models.test_failure import TestFailure, FixSuggestion
from ...utils.resource_manager import TimeoutError


@pytest.fixture
def test_failure():
    """Provide a TestFailure instance for testing."""
    return TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="E       assert 1 == 2\nE       +  where 1 = func()",
        line_number=42,
        relevant_code="def test_function():\n    assert 1 == 2"
    )


@pytest.fixture
def failure_analyzer():
    """Provide a FailureAnalyzer instance for testing."""
    return FailureAnalyzer()


def test_init_patterns(failure_analyzer):
    """Test initialization of error patterns."""
    assert 'AssertionError' in failure_analyzer.error_analyzers
    assert 'AttributeError' in failure_analyzer.error_analyzers
    assert 'ImportError' in failure_analyzer.error_analyzers
    assert 'TypeError' in failure_analyzer.error_analyzers
    assert callable(failure_analyzer.error_analyzers['AssertionError'])


def test_analyze_failure(failure_analyzer, test_failure):
    """Test analyzing a test failure."""
    # Analyze the failure
    suggestions = failure_analyzer.analyze_failure(test_failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_analyze_failure_max_suggestions(test_failure):
    """Test limiting the number of suggestions."""
    # Create a FailureAnalyzer with a max_suggestions limit
    analyzer = FailureAnalyzer(max_suggestions=2)
    
    # Mock the _analyze_assertion_error method to return more suggestions than the limit
    analyzer._analyze_assertion_error = MagicMock(return_value=[
        FixSuggestion(failure=test_failure, suggestion="Suggestion 1", confidence=0.8),
        FixSuggestion(failure=test_failure, suggestion="Suggestion 2", confidence=0.7),
        FixSuggestion(failure=test_failure, suggestion="Suggestion 3", confidence=0.6)
    ])
    
    # Analyze the failure
    suggestions = analyzer.analyze_failure(test_failure)
    
    # Verify the results
    assert len(suggestions) == 2  # Limited to max_suggestions


@patch('logging.Logger.error')
def test_analyze_failure_exception(mock_logger_error, failure_analyzer, test_failure):
    """Test error handling during failure analysis."""
    # Mock the _get_base_error_type method to raise an exception
    failure_analyzer._get_base_error_type = MagicMock(side_effect=Exception("Test error"))
    
    # Analyze the failure
    suggestions = failure_analyzer.analyze_failure(test_failure)
    
    # Verify the results
    assert suggestions == []  # Empty list on error
    mock_logger_error.assert_called_once()


def test_get_base_error_type(failure_analyzer):
    """Test extracting the base error type."""
    # Test with qualified name
    assert failure_analyzer._get_base_error_type("unittest.AssertionError") == "AssertionError"
    
    # Test with simple name
    assert failure_analyzer._get_base_error_type("ValueError") == "ValueError"
    
    # Test with empty string
    assert failure_analyzer._get_base_error_type("") == ""


@pytest.mark.parametrize("error_type,analyzer_method", [
    ("AssertionError", "_analyze_assertion_error"),
    ("AttributeError", "_analyze_attribute_error"),
    ("ImportError", "_analyze_import_error"),
    ("TypeError", "_analyze_type_error"),
    ("NameError", "_analyze_name_error"),
    ("IndexError", "_analyze_index_error"),
    ("KeyError", "_analyze_key_error"),
    ("ValueError", "_analyze_value_error"),
    ("SyntaxError", "_analyze_syntax_error"),
    ("UnknownError", "_analyze_generic_error")
])
def test_error_type_mapping(failure_analyzer, test_failure, error_type, analyzer_method):
    """Test mapping of error types to analyzer methods."""
    # Mock all analyzer methods
    for method_name in failure_analyzer.error_analyzers.values():
        setattr(failure_analyzer, method_name.__name__, MagicMock(return_value=[]))
    
    # Set the error type
    test_failure.error_type = error_type
    
    # Analyze the failure
    failure_analyzer.analyze_failure(test_failure)
    
    # Verify that the correct analyzer method was called
    method = getattr(failure_analyzer, analyzer_method)
    assert method.called


def test_analyze_assertion_error(failure_analyzer, test_failure):
    """Test analyzing an assertion error."""
    # Analyze the assertion error
    suggestions = failure_analyzer._analyze_assertion_error(test_failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_analyze_assert_statement(failure_analyzer, test_failure):
    """Test analyzing an assert statement."""
    # Set up a traceback with an equality assertion
    test_failure.traceback = "E       assert first_value == second_value"
    
    # Analyze the assert statement
    suggestion, confidence = failure_analyzer._analyze_assert_statement(test_failure)
    
    # Verify the results
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0
    assert isinstance(confidence, float)
    assert 0.0 <= confidence <= 1.0


def test_analyze_assert_statement_with_expected_actual(failure_analyzer, test_failure):
    """Test analyzing an assert statement with expected vs. actual values."""
    # Set up a traceback with expected vs. actual values
    test_failure.traceback = "E       assert actual_value == expected_value\nE         +  where actual_value = func()"
    
    # Analyze the assert statement
    suggestion, confidence = failure_analyzer._analyze_assert_statement(test_failure)
    
    # Verify the results
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0
    assert isinstance(confidence, float)
    assert 0.0 <= confidence <= 1.0


def test_analyze_assert_statement_in_operator(failure_analyzer, test_failure):
    """Test analyzing an assert statement with the 'in' operator."""
    # Set up a traceback with an 'in' assertion
    test_failure.traceback = "E       assert item in container"
    
    # Analyze the assert statement
    suggestion, confidence = failure_analyzer._analyze_assert_statement(test_failure)
    
    # Verify the results
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0
    assert isinstance(confidence, float)
    assert 0.0 <= confidence <= 1.0


def test_analyze_assert_statement_is_true(failure_analyzer, test_failure):
    """Test analyzing an assert statement checking for True."""
    # Set up a traceback with a True assertion
    test_failure.traceback = "E       assert condition is True"
    
    # Analyze the assert statement
    suggestion, confidence = failure_analyzer._analyze_assert_statement(test_failure)
    
    # Verify the results
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0
    assert isinstance(confidence, float)
    assert 0.0 <= confidence <= 1.0


def test_analyze_assert_statement_no_match(failure_analyzer, test_failure):
    """Test analyzing an assert statement with no recognizable pattern."""
    # Set up a traceback with no recognizable pattern
    test_failure.traceback = "E       some random text"
    
    # Analyze the assert statement
    suggestion, confidence = failure_analyzer._analyze_assert_statement(test_failure)
    
    # Verify the results
    assert suggestion == ""
    assert confidence == 0.0


# Add similar tests for other analyzer methods (_analyze_attribute_error, _analyze_import_error, etc.)
# Each test should verify that the method returns a list of FixSuggestion objects

def test_analyze_attribute_error(failure_analyzer):
    """Test analyzing an attribute error."""
    # Create a test failure with an attribute error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AttributeError",
        error_message="'NoneType' object has no attribute 'value'",
        traceback="E       AttributeError: 'NoneType' object has no attribute 'value'",
        line_number=42
    )
    
    # Analyze the attribute error
    suggestions = failure_analyzer._analyze_attribute_error(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_analyze_import_error(failure_analyzer):
    """Test analyzing an import error."""
    # Create a test failure with an import error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="ImportError",
        error_message="No module named 'nonexistent_module'",
        traceback="E       ImportError: No module named 'nonexistent_module'",
        line_number=42
    )
    
    # Analyze the import error
    suggestions = failure_analyzer._analyze_import_error(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_analyze_type_error(failure_analyzer):
    """Test analyzing a type error."""
    # Create a test failure with a type error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="TypeError",
        error_message="function() takes 2 positional arguments but 3 were given",
        traceback="E       TypeError: function() takes 2 positional arguments but 3 were given",
        line_number=42
    )
    
    # Analyze the type error
    suggestions = failure_analyzer._analyze_type_error(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_analyze_generic_error(failure_analyzer):
    """Test analyzing a generic error."""
    # Create a test failure with a generic error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="CustomError",
        error_message="Something went wrong",
        traceback="E       CustomError: Something went wrong",
        line_number=42
    )
    
    # Analyze the generic error
    suggestions = failure_analyzer._analyze_generic_error(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)