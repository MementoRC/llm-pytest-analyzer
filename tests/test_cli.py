"""Tests for the CLI module."""

import pytest
from unittest.mock import patch
from pathlib import Path
import sys

from ..cli.analyzer_cli import main, setup_parser, configure_settings


def test_parser_setup():
    """Test that the argument parser is set up correctly."""
    parser = setup_parser()
    args = parser.parse_args(['test_path'])
    assert args.test_path == 'test_path'
    assert args.debug is False
    assert args.max_failures == 100


@patch('pytest_analyzer.core.analyzer_service.TestAnalyzerService')
@patch('pytest_analyzer.cli.analyzer_cli.display_suggestions')
def test_cli_main_with_test_path(mock_display, mock_service):
    """Test the main function with a test path."""
    # Setup
    mock_analyzer = mock_service.return_value
    mock_analyzer.run_and_analyze.return_value = ['suggestion1', 'suggestion2']
    
    # Execute
    with patch.object(sys, 'argv', ['pytest-analyzer', 'test_path']):
        result = main()
    
    # Assert
    mock_service.assert_called_once()
    mock_analyzer.run_and_analyze.assert_called_once()
    mock_display.assert_called_once_with(['suggestion1', 'suggestion2'], pytest.ANY)
    assert result == 0  # Success


@patch('pytest_analyzer.core.analyzer_service.TestAnalyzerService')
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
    mock_display.assert_called_once_with(['suggestion1'], pytest.ANY)
    assert result == 0  # Success


@patch('pytest_analyzer.core.analyzer_service.TestAnalyzerService')
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
    mock_display.assert_called_once_with([], pytest.ANY)
    assert result == 1  # No suggestions


@patch('pytest_analyzer.core.analyzer_service.TestAnalyzerService')
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
        '--pytest-args', '--verbose',
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