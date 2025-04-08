"""Tests for the fix suggester module."""
import pytest
import re
from unittest.mock import patch, MagicMock

from ...core.analysis.fix_suggester import FixSuggester
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
def fix_suggester():
    """Provide a FixSuggester instance for testing."""
    return FixSuggester()


def test_suggest_fixes(fix_suggester, test_failure):
    """Test suggesting fixes for a test failure."""
    # Mock the _generate_suggestions method to return a known result
    fix_suggester._generate_suggestions = MagicMock(return_value=[
        FixSuggestion(failure=test_failure, suggestion="Fix 1", confidence=0.8),
        FixSuggestion(failure=test_failure, suggestion="Fix 2", confidence=0.6),
        FixSuggestion(failure=test_failure, suggestion="Fix 3", confidence=0.4)
    ])
    
    # Suggest fixes
    suggestions = fix_suggester.suggest_fixes(test_failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) == 2  # Only suggestions with confidence >= 0.5 should be returned
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)
    assert all(suggestion.confidence >= 0.5 for suggestion in suggestions)


def test_suggest_fixes_min_confidence(test_failure):
    """Test minimum confidence filtering."""
    # Create a FixSuggester with a custom min_confidence
    suggester = FixSuggester(min_confidence=0.7)
    
    # Mock the _generate_suggestions method to return a known result
    suggester._generate_suggestions = MagicMock(return_value=[
        FixSuggestion(failure=test_failure, suggestion="Fix 1", confidence=0.8),
        FixSuggestion(failure=test_failure, suggestion="Fix 2", confidence=0.6),
        FixSuggestion(failure=test_failure, suggestion="Fix 3", confidence=0.4)
    ])
    
    # Suggest fixes
    suggestions = suggester.suggest_fixes(test_failure)
    
    # Verify the results
    assert len(suggestions) == 1  # Only suggestions with confidence >= 0.7 should be returned
    assert suggestions[0].suggestion == "Fix 1"


@patch('logging.Logger.error')
def test_suggest_fixes_exception(mock_logger_error, fix_suggester, test_failure):
    """Test error handling during fix suggestion."""
    # Mock the _generate_suggestions method to raise an exception
    fix_suggester._generate_suggestions = MagicMock(side_effect=Exception("Test error"))
    
    # Suggest fixes
    suggestions = fix_suggester.suggest_fixes(test_failure)
    
    # Verify the results
    assert suggestions == []  # Empty list on error
    mock_logger_error.assert_called_once()


def test_generate_suggestions(fix_suggester, test_failure):
    """Test generating suggestions based on error type."""
    # Mock the suggestion methods to return known results
    fix_suggester._suggest_assertion_fixes = MagicMock(return_value=["Assertion fix"])
    fix_suggester._suggest_attribute_fixes = MagicMock(return_value=["Attribute fix"])
    fix_suggester._suggest_import_fixes = MagicMock(return_value=["Import fix"])
    fix_suggester._suggest_type_fixes = MagicMock(return_value=["Type fix"])
    fix_suggester._suggest_name_fixes = MagicMock(return_value=["Name fix"])
    fix_suggester._suggest_syntax_fixes = MagicMock(return_value=["Syntax fix"])
    fix_suggester._suggest_generic_fixes = MagicMock(return_value=["Generic fix"])
    
    # Generate suggestions for different error types
    assert fix_suggester._generate_suggestions(TestFailure(error_type="AssertionError")) == ["Assertion fix"]
    assert fix_suggester._generate_suggestions(TestFailure(error_type="AttributeError")) == ["Attribute fix"]
    assert fix_suggester._generate_suggestions(TestFailure(error_type="ImportError")) == ["Import fix"]
    assert fix_suggester._generate_suggestions(TestFailure(error_type="TypeError")) == ["Type fix"]
    assert fix_suggester._generate_suggestions(TestFailure(error_type="NameError")) == ["Name fix"]
    assert fix_suggester._generate_suggestions(TestFailure(error_type="SyntaxError")) == ["Syntax fix"]
    assert fix_suggester._generate_suggestions(TestFailure(error_type="UnknownError")) == ["Generic fix"]


def test_suggest_assertion_fixes(fix_suggester):
    """Test suggesting fixes for assertion errors."""
    # Create a test failure with an assertion error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="E       assert 1 == 2\nE       +  where 1 = func()",
        line_number=42
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_assertion_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_suggest_assertion_fixes_with_exp_vs_act(fix_suggester):
    """Test suggesting fixes for assertion errors with expected vs. actual values."""
    # Create a test failure with an assertion error and expected vs. actual values
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="E       assert 1 == 2\nE         where 1 = actual()\nE         and 2 = expected()",
        line_number=42
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_assertion_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_suggest_attribute_fixes(fix_suggester):
    """Test suggesting fixes for attribute errors."""
    # Create a test failure with an attribute error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AttributeError",
        error_message="'NoneType' object has no attribute 'value'",
        traceback="E       AttributeError: 'NoneType' object has no attribute 'value'",
        line_number=42
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_attribute_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_suggest_import_fixes(fix_suggester):
    """Test suggesting fixes for import errors."""
    # Create a test failure with an import error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="ImportError",
        error_message="No module named 'nonexistent_module'",
        traceback="E       ImportError: No module named 'nonexistent_module'",
        line_number=42
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_import_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_suggest_import_fixes_with_package(fix_suggester):
    """Test suggesting fixes for import errors with package paths."""
    # Create a test failure with an import error for a package path
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="ImportError",
        error_message="No module named 'package.subpackage.module'",
        traceback="E       ImportError: No module named 'package.subpackage.module'",
        line_number=42
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_import_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_suggest_type_fixes(fix_suggester):
    """Test suggesting fixes for type errors."""
    # Create a test failure with a type error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="TypeError",
        error_message="function() takes 2 positional arguments but 3 were given",
        traceback="E       TypeError: function() takes 2 positional arguments but 3 were given",
        line_number=42
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_type_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_suggest_type_fixes_unexpected_keyword(fix_suggester):
    """Test suggesting fixes for type errors with unexpected keyword arguments."""
    # Create a test failure with a type error for an unexpected keyword argument
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="TypeError",
        error_message="got an unexpected keyword argument 'unknown_param'",
        traceback="E       TypeError: got an unexpected keyword argument 'unknown_param'",
        line_number=42
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_type_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_suggest_name_fixes(fix_suggester):
    """Test suggesting fixes for name errors."""
    # Create a test failure with a name error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="NameError",
        error_message="name 'undefined_variable' is not defined",
        traceback="E       NameError: name 'undefined_variable' is not defined",
        line_number=42
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_name_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_suggest_syntax_fixes(fix_suggester):
    """Test suggesting fixes for syntax errors."""
    # Create a test failure with a syntax error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="SyntaxError",
        error_message="invalid syntax",
        traceback="E       SyntaxError: invalid syntax",
        line_number=42,
        relevant_code="def test_function():\n    if condition"  # Missing colon
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_syntax_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_suggest_syntax_fixes_missing_parenthesis(fix_suggester):
    """Test suggesting fixes for syntax errors with missing parenthesis."""
    # Create a test failure with a syntax error for missing parenthesis
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="SyntaxError",
        error_message="invalid syntax",
        traceback="E       SyntaxError: invalid syntax",
        line_number=42,
        relevant_code="def test_function():\n    print('hello'"  # Missing closing parenthesis
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_syntax_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)


def test_suggest_generic_fixes(fix_suggester):
    """Test suggesting fixes for generic errors."""
    # Create a test failure with a generic error
    failure = TestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="CustomError",
        error_message="Something went wrong",
        traceback="E       CustomError: Something went wrong",
        line_number=42
    )
    
    # Suggest fixes
    suggestions = fix_suggester._suggest_generic_fixes(failure)
    
    # Verify the results
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0
    assert all(isinstance(suggestion, FixSuggestion) for suggestion in suggestions)