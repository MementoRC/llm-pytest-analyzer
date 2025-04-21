"""Tests for the CLI module."""

import pytest
from unittest.mock import patch, MagicMock, ANY
import sys
import argparse
import logging

from pytest_analyzer.cli.analyzer_cli import main, setup_parser, configure_settings, display_suggestions
from pytest_analyzer.core.models.pytest_failure import PytestFailure, FixSuggestion


@pytest.fixture
def mock_console():
    """Mock console for capturing output."""
    with patch('pytest_analyzer.cli.analyzer_cli.console') as mock_console:
        yield mock_console


@pytest.fixture
def test_failure():
    """Fixture for a test failure."""
    return PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="E       assert 1 == 2\nE       +  where 1 = func()",
        line_number=42,
        relevant_code="def test_function():\n    assert 1 == 2"
    )


@pytest.fixture
def test_suggestion(test_failure):
    """Fixture for a test suggestion."""
    return FixSuggestion(
        failure=test_failure,
        suggestion="Fix the assertion to expect 1 instead of 2",
        confidence=0.8,
        explanation="The test expected 2 but got 1"
    )


@pytest.fixture
def llm_suggestion(test_failure):
    """Fixture for an LLM-based suggestion."""
    return FixSuggestion(
        failure=test_failure,
        suggestion="Use assertEqual(1, 2) for better error messages",
        confidence=0.9,
        explanation="Using assertEqual provides more detailed failure output",
        code_changes={
            "source": "llm",
            "test_file.py": "def test_function():\n    assertEqual(1, 2)"
        }
    )


@pytest.fixture
def mock_args():
    """Fixture for mock command-line arguments."""
    return argparse.Namespace(verbosity=1)


@patch('pytest_analyzer.cli.analyzer_cli.PytestAnalyzerService')
@patch('pytest_analyzer.cli.analyzer_cli.display_suggestions')
def test_cli_main_success(mock_display, mock_service):
    """Test the main function with successful operation."""
    # Setup
    mock_analyzer = mock_service.return_value
    mock_analyzer.run_and_analyze.return_value = ['suggestion1', 'suggestion2']
    
    # Execute
    with patch.object(sys, 'argv', ['pytest-analyzer', 'test_path']):
        result = main()
    
    # Assert
    mock_service.assert_called_once()
    mock_analyzer.run_and_analyze.assert_called_once()
    mock_display.assert_called_once_with(['suggestion1', 'suggestion2'], ANY)
    assert result == 0  # Success


@patch('pytest_analyzer.cli.analyzer_cli.PytestAnalyzerService')
@patch('pytest_analyzer.cli.analyzer_cli.display_suggestions')
def test_cli_main_with_output_file(mock_display, mock_service):
    """Test the main function with an output file."""
    # Setup
    mock_analyzer = mock_service.return_value
    mock_analyzer.analyze_pytest_output.return_value = ['suggestion1']
    
    # Execute
    with patch.object(sys, 'argv', ['pytest-analyzer', 'test_path', '--output-file', 'output.json']):
        result = main()
    
    # Assert
    mock_service.assert_called_once()
    mock_analyzer.analyze_pytest_output.assert_called_once_with('output.json')
    mock_display.assert_called_once_with(['suggestion1'], ANY)
    assert result == 0  # Success


@patch('pytest_analyzer.cli.analyzer_cli.PytestAnalyzerService')
@patch('pytest_analyzer.cli.analyzer_cli.display_suggestions')
def test_cli_main_no_suggestions(mock_display, mock_service):
    """Test the main function when no suggestions are found."""
    # Setup
    mock_analyzer = mock_service.return_value
    mock_analyzer.run_and_analyze.return_value = []
    
    # Execute
    with patch.object(sys, 'argv', ['pytest-analyzer', 'test_path']):
        result = main()
    
    # Assert
    mock_service.assert_called_once()
    mock_analyzer.run_and_analyze.assert_called_once()
    mock_display.assert_called_once_with([], ANY)
    assert result == 1  # No suggestions


@patch('pytest_analyzer.cli.analyzer_cli.PytestAnalyzerService')
def test_cli_main_exception(mock_service):
    """Test the main function when an exception occurs."""
    # Setup
    mock_analyzer = mock_service.return_value
    mock_analyzer.run_and_analyze.side_effect = Exception("Test error")
    
    # Execute
    with patch.object(sys, 'argv', ['pytest-analyzer', 'test_path']):
        result = main()
    
    # Assert
    mock_service.assert_called_once()
    mock_analyzer.run_and_analyze.assert_called_once()
    assert result == 2  # Error


@patch('pytest_analyzer.cli.analyzer_cli.PytestAnalyzerService')
@patch('logging.getLogger')
@patch('pytest_analyzer.cli.analyzer_cli.display_suggestions')
def test_cli_main_with_debug(mock_display, mock_logging, mock_service):
    """Test the main function with debug logging enabled."""
    # Setup
    mock_logger = MagicMock()
    mock_logging.return_value = mock_logger
    mock_analyzer = mock_service.return_value
    
    # Create a proper suggestion with a failure attribute
    test_failure = PytestFailure(
        test_name="test_file.py::test_function",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="E       assert 1 == 2\nE       +  where 1 = func()",
        line_number=42
    )
    
    suggestion = FixSuggestion(
        failure=test_failure,
        suggestion="Fix the assertion",
        confidence=0.8
    )
    
    mock_analyzer.run_and_analyze.return_value = [suggestion]
    
    # Execute
    with patch.object(sys, 'argv', ['pytest-analyzer', 'test_path', '--debug']):
        result = main()
    
    # Assert
    mock_logging.assert_called()
    mock_logger.setLevel.assert_called_with(logging.DEBUG)
    assert result == 0  # Success


def test_configure_settings():
    """Test that settings are configured correctly from arguments."""
    parser = setup_parser()
    args = parser.parse_args([
        'test_path',
        '--json',
        '--max-failures', '10',
        '--max-suggestions', '5',
        '--min-confidence', '0.8',
        '--timeout', '600',
        '--max-memory', '2048',
        '--pytest-args', '--verbose --xvs',  # Quote the arguments
        '--coverage'
    ])
    
    settings = configure_settings(args)
    
    assert settings.max_failures == 10
    assert settings.max_suggestions == 5
    assert settings.min_confidence == 0.8
    assert settings.pytest_timeout == 600
    assert settings.max_memory_mb == 2048
    assert settings.preferred_format == 'json'
    assert '--verbose' in settings.pytest_args
    assert '--cov' in settings.pytest_args


def test_configure_settings_with_config_file():
    """Test settings configuration with a config file.
    
    Note: We're testing this without mocking load_settings since
    it's difficult to mock correctly due to import path.
    """
    # Create a parser and args with config file
    parser = setup_parser()
    args = parser.parse_args([
        'test_path',
        '--config-file', 'config.json',
        '--max-failures', '10',  # Should override default
    ])
    
    # Execute
    settings = configure_settings(args)
    
    # Assert basic expectations
    assert settings.max_failures == 10  # Updated from command line


def test_configure_settings_with_test_functions():
    """Test settings configuration with test function filtering."""
    parser = setup_parser()
    args = parser.parse_args([
        'test_path',
        '-k', 'test_specific_function'
    ])
    
    settings = configure_settings(args)
    
    assert '-k' in settings.pytest_args
    assert 'test_specific_function' in settings.pytest_args


def test_configure_settings_with_llm_options():
    """Test settings configuration with LLM options."""
    parser = setup_parser()
    args = parser.parse_args([
        'test_path',
        '--use-llm',
        '--llm-timeout', '120',
        '--llm-api-key', 'test-key',
        '--llm-model', 'custom-model'
    ])
    
    settings = configure_settings(args)
    
    assert settings.use_llm is True
    assert settings.llm_timeout == 120
    assert settings.llm_api_key == 'test-key'
    assert settings.llm_model == 'custom-model'


def test_display_suggestions_empty(mock_console):
    """Test displaying empty suggestions."""
    # Call the function with empty suggestions
    display_suggestions([], argparse.Namespace(verbosity=1))
    
    # Verify that the appropriate message is displayed
    mock_console.print.assert_called_with("\n[bold red]No fix suggestions found.[/bold red]")


def test_display_suggestions_with_rule_based(mock_console, test_suggestion, mock_args):
    """Test displaying rule-based suggestions."""
    # Call the function with a rule-based suggestion
    display_suggestions([test_suggestion], mock_args)
    
    # Verify key calls
    mock_console.print.assert_any_call("\n[bold green]Found 1 fix suggestions:[/bold green]")
    mock_console.print.assert_any_call("\n[bold green]Suggested fix (Rule-based):[/bold green]")
    mock_console.print.assert_any_call(test_suggestion.suggestion)


def test_display_suggestions_with_llm(mock_console, llm_suggestion, mock_args):
    """Test displaying LLM-based suggestions."""
    # Call the function with an LLM-based suggestion
    display_suggestions([llm_suggestion], mock_args)
    
    # Verify key calls
    mock_console.print.assert_any_call("\n[bold green]Found 1 fix suggestions:[/bold green]")
    mock_console.print.assert_any_call("\n[bold yellow]Suggested fix (LLM):[/bold yellow]")
    mock_console.print.assert_any_call(llm_suggestion.suggestion)


@patch('pytest_analyzer.cli.analyzer_cli.Syntax')
def test_display_suggestions_with_code_changes(mock_syntax, mock_console, test_suggestion, mock_args):
    """Test displaying suggestions with code changes."""
    # Add code changes to the suggestion
    test_suggestion.code_changes = {"test_file.py": "def fixed_test():\n    assert 1 == 1"}
    
    # Call the function
    display_suggestions([test_suggestion], mock_args)
    
    # Verify key calls
    mock_console.print.assert_any_call("\n[bold cyan]Code changes:[/bold cyan]")
    mock_console.print.assert_any_call("\n[bold]File:[/bold] test_file.py")
    
    # Verify that Syntax was called at least once 
    # (might be called twice if relevant_code is also displayed)
    assert mock_syntax.call_count >= 1