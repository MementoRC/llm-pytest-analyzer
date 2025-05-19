"""Tests for the failure analyzer module."""

from unittest.mock import MagicMock, patch

import pytest

from src.pytest_analyzer.core.analysis.failure_analyzer import FailureAnalyzer
from src.pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure


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
def failure_analyzer():
    """Provide a FailureAnalyzer instance for testing."""
    return FailureAnalyzer()


def test_init_patterns(failure_analyzer):
    """Test initialization of error patterns."""
    assert "AssertionError" in failure_analyzer.error_analyzers
    assert "AttributeError" in failure_analyzer.error_analyzers
    assert "ImportError" in failure_analyzer.error_analyzers
    assert "TypeError" in failure_analyzer.error_analyzers
    assert callable(failure_analyzer.error_analyzers["AssertionError"])


def test_analyze_failure(failure_analyzer, test_failure):
    """Test analyzing a test failure."""
    # Analyze the failure
    suggestions = failure_analyzer.analyze_failure(test_failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_analyze_failure_max_suggestions(failure_analyzer):
    """Test limiting the number of suggestions."""
    # Verify that the max_suggestions attribute exists
    assert hasattr(failure_analyzer, "max_suggestions")

    # Create a custom analyzer with a lower max_suggestions limit
    analyzer_with_limit = FailureAnalyzer(max_suggestions=1)
    assert analyzer_with_limit.max_suggestions == 1

    # Create a custom analyzer with a higher max_suggestions limit
    analyzer_with_higher_limit = FailureAnalyzer(max_suggestions=5)
    assert analyzer_with_higher_limit.max_suggestions == 5

    # Verify the default max_suggestions
    default_analyzer = FailureAnalyzer()
    assert default_analyzer.max_suggestions >= 1


@patch("logging.Logger.error")
def test_analyze_failure_exception(mock_logger_error, failure_analyzer, test_failure):
    """Test error handling during failure analysis."""
    # Mock the _get_base_error_type method to raise an exception
    failure_analyzer._get_base_error_type = MagicMock(
        side_effect=Exception("Test error")
    )

    # Analyze the failure
    suggestions = failure_analyzer.analyze_failure(test_failure)

    # Verify the results
    assert suggestions == []  # Empty list on error
    mock_logger_error.assert_called_once()


def test_get_base_error_type(failure_analyzer):
    """Test extracting the base error type."""
    # Test with qualified name
    assert (
        failure_analyzer._get_base_error_type("unittest.AssertionError")
        == "AssertionError"
    )

    # Test with simple name
    assert failure_analyzer._get_base_error_type("ValueError") == "ValueError"

    # Test with empty string
    assert failure_analyzer._get_base_error_type("") == ""


def test_error_type_mapping(failure_analyzer):
    """Test mapping of error types to analyzer methods."""
    # Verify all the required methods are in the dictionary
    assert "AssertionError" in failure_analyzer.error_analyzers
    assert "AttributeError" in failure_analyzer.error_analyzers
    assert "ImportError" in failure_analyzer.error_analyzers
    assert "TypeError" in failure_analyzer.error_analyzers
    assert "NameError" in failure_analyzer.error_analyzers
    assert "IndexError" in failure_analyzer.error_analyzers
    assert "KeyError" in failure_analyzer.error_analyzers
    assert "ValueError" in failure_analyzer.error_analyzers
    assert "SyntaxError" in failure_analyzer.error_analyzers

    # Verify that the method references are correct
    assert (
        failure_analyzer.error_analyzers["AssertionError"].__name__
        == "_analyze_assertion_error"
    )
    assert (
        failure_analyzer.error_analyzers["AttributeError"].__name__
        == "_analyze_attribute_error"
    )
    assert (
        failure_analyzer.error_analyzers["ImportError"].__name__
        == "_analyze_import_error"
    )
    assert (
        failure_analyzer.error_analyzers["TypeError"].__name__ == "_analyze_type_error"
    )
    assert (
        failure_analyzer.error_analyzers["NameError"].__name__ == "_analyze_name_error"
    )
    assert (
        failure_analyzer.error_analyzers["IndexError"].__name__
        == "_analyze_index_error"
    )
    assert failure_analyzer.error_analyzers["KeyError"].__name__ == "_analyze_key_error"
    assert (
        failure_analyzer.error_analyzers["ValueError"].__name__
        == "_analyze_value_error"
    )
    assert (
        failure_analyzer.error_analyzers["SyntaxError"].__name__
        == "_analyze_syntax_error"
    )

    # Test the fallback mechanism
    assert (
        failure_analyzer._get_base_error_type("UnknownError")
        not in failure_analyzer.error_analyzers
    )


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


def test_analyze_attribute_error(failure_analyzer):
    """Test analyzing an attribute error."""
    # Create a test failure with an attribute error
    failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AttributeError",
        error_message="'NoneType' object has no attribute 'value'",
        traceback="E       AttributeError: 'NoneType' object has no attribute 'value'",
        line_number=42,
    )

    # Analyze the attribute error
    suggestions = failure_analyzer._analyze_attribute_error(failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)

    # Test with a different attribute error message format
    failure.error_message = "Something went wrong with an attribute"
    suggestions = failure_analyzer._analyze_attribute_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


def test_analyze_import_error(failure_analyzer):
    """Test analyzing an import error."""
    # Create a test failure with an import error
    failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="ImportError",
        error_message="No module named 'nonexistent_module'",
        traceback="E       ImportError: No module named 'nonexistent_module'",
        line_number=42,
    )

    # Analyze the import error
    suggestions = failure_analyzer._analyze_import_error(failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)

    # Test with a package import
    failure.error_message = "No module named 'package.submodule'"
    suggestions = failure_analyzer._analyze_import_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # Test with a different import error message format
    failure.error_message = "Something went wrong with an import"
    suggestions = failure_analyzer._analyze_import_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


def test_analyze_type_error(failure_analyzer):
    """Test analyzing a type error."""
    # Create a test failure with a type error (incorrect argument count)
    failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="TypeError",
        error_message="function() takes 2 positional arguments but 3 were given",
        traceback="E       TypeError: function() takes 2 positional arguments but 3 were given",
        line_number=42,
    )

    # Analyze the type error
    suggestions = failure_analyzer._analyze_type_error(failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)

    # Test with unexpected keyword argument
    failure.error_message = "got an unexpected keyword argument 'invalid_param'"
    suggestions = failure_analyzer._analyze_type_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # Test with sequence multiplication error
    failure.error_message = "can't multiply sequence by non-int of type 'float'"
    suggestions = failure_analyzer._analyze_type_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # Test with a different type error message format
    failure.error_message = "Something went wrong with a type"
    suggestions = failure_analyzer._analyze_type_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


def test_analyze_name_error(failure_analyzer):
    """Test analyzing a name error."""
    # Create a test failure with a name error
    failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="NameError",
        error_message="name 'undefined_variable' is not defined",
        traceback="E       NameError: name 'undefined_variable' is not defined",
        line_number=42,
    )

    # Analyze the name error
    suggestions = failure_analyzer._analyze_name_error(failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)

    # Test with a different name error message format
    failure.error_message = "Something went wrong with a name"
    suggestions = failure_analyzer._analyze_name_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


def test_analyze_index_error(failure_analyzer):
    """Test analyzing an index error."""
    # Create a test failure with an index error
    failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="IndexError",
        error_message="list index out of range",
        traceback="E       IndexError: list index out of range",
        line_number=42,
    )

    # Analyze the index error
    suggestions = failure_analyzer._analyze_index_error(failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)

    # Test with a different index error message format
    failure.error_message = "Something went wrong with an index"
    suggestions = failure_analyzer._analyze_index_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


def test_analyze_key_error(failure_analyzer):
    """Test analyzing a key error."""
    # Create a test failure with a key error
    failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="KeyError",
        error_message="KeyError: 'missing_key'",
        traceback="E       KeyError: 'missing_key'",
        line_number=42,
    )

    # Analyze the key error
    suggestions = failure_analyzer._analyze_key_error(failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)

    # Test with a different key error message format (without quotes)
    failure.error_message = "KeyError: missing_key"
    suggestions = failure_analyzer._analyze_key_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # Test with a different key error message format (not matched)
    failure.error_message = "Something went wrong with a key"
    suggestions = failure_analyzer._analyze_key_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


def test_analyze_value_error(failure_analyzer):
    """Test analyzing a value error."""
    # Create a test failure with a value error (invalid int conversion)
    failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="ValueError",
        error_message="invalid literal for int() with base 10: 'abc'",
        traceback="E       ValueError: invalid literal for int() with base 10: 'abc'",
        line_number=42,
    )

    # Analyze the value error
    suggestions = failure_analyzer._analyze_value_error(failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)

    # Test with a different value error message format
    failure.error_message = "Something went wrong with a value"
    suggestions = failure_analyzer._analyze_value_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


def test_analyze_syntax_error(failure_analyzer):
    """Test analyzing a syntax error."""
    # Create a test failure with a syntax error
    failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="SyntaxError",
        error_message="invalid syntax",
        traceback="E       SyntaxError: invalid syntax",
        line_number=42,
    )

    # Analyze the syntax error
    suggestions = failure_analyzer._analyze_syntax_error(failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)

    # Test with relevant code containing different syntax errors

    # Missing closing parenthesis
    failure.relevant_code = "def function(x, y:"
    suggestions = failure_analyzer._analyze_syntax_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # Missing closing bracket
    failure.relevant_code = "items = [1, 2, 3"
    suggestions = failure_analyzer._analyze_syntax_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # Missing closing brace
    failure.relevant_code = "data = {'key': 'value'"
    suggestions = failure_analyzer._analyze_syntax_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # Missing colon in if statement
    failure.relevant_code = "if condition"
    suggestions = failure_analyzer._analyze_syntax_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # No relevant code
    failure.relevant_code = None
    suggestions = failure_analyzer._analyze_syntax_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


def test_analyze_generic_error(failure_analyzer):
    """Test analyzing a generic error."""
    # Create a test failure with a generic error
    failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="CustomError",
        error_message="Something went wrong",
        traceback="E       CustomError: Something went wrong",
        line_number=42,
    )

    # Analyze the generic error
    suggestions = failure_analyzer._analyze_generic_error(failure)

    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)

    # Test without a line number
    failure.line_number = None
    suggestions = failure_analyzer._analyze_generic_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # Test with relevant code
    failure.relevant_code = (
        "def function():\n    raise CustomError('Something went wrong')"
    )
    suggestions = failure_analyzer._analyze_generic_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    # Test without relevant code
    failure.relevant_code = None
    suggestions = failure_analyzer._analyze_generic_error(failure)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


# This test is removed as it's not correctly mocking the with_timeout decorator
# The with_timeout decorator is applied at the time the class is defined,
# not when the method is called, so it can't be easily mocked this way
