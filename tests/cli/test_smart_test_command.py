"""
Tests for the SmartTestCommand CLI Command.

Simple tests that work with the current implementation.
"""

from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.cli.smart_test import SmartTestCommand, main


def test_smart_test_command_initialization():
    """Test that SmartTestCommand can be initialized."""
    command = SmartTestCommand()
    assert command is not None
    assert command.test_categorizer is not None
    assert command.token_analyzer is not None


@patch("sys.argv", ["smart-test", "--help"])
def test_parse_arguments_help():
    """Test that help argument is handled properly."""
    command = SmartTestCommand()

    with pytest.raises(SystemExit) as exc_info:
        command.parse_arguments()

    # argparse exits with code 0 for help
    assert exc_info.value.code == 0


@patch("sys.argv", ["smart-test"])
def test_parse_arguments_no_args():
    """Test parsing with no arguments."""
    command = SmartTestCommand()
    args = command.parse_arguments()

    assert args is not None
    assert not hasattr(args, "all") or not args.all
    assert not hasattr(args, "json") or not args.json
    assert not hasattr(args, "verbose") or not args.verbose


@patch("sys.argv", ["smart-test", "--json"])
def test_parse_arguments_json():
    """Test parsing with JSON flag."""
    command = SmartTestCommand()
    args = command.parse_arguments()

    assert args.json is True


@patch("sys.argv", ["smart-test", "--all"])
def test_parse_arguments_all():
    """Test parsing with all flag."""
    command = SmartTestCommand()
    args = command.parse_arguments()

    assert args.all is True


@patch("sys.argv", ["smart-test", "--category", "unit"])
def test_parse_arguments_category():
    """Test parsing with category."""
    command = SmartTestCommand()
    args = command.parse_arguments()

    assert args.category == "unit"


def test_categorize_tests_with_no_files():
    """Test categorize_tests when no test files are found."""
    command = SmartTestCommand()

    # Mock _find_test_files to return empty list
    with patch.object(command, "_find_test_files", return_value=[]):
        args = MagicMock()
        result = command.categorize_tests(args)

        assert isinstance(result, dict)
        assert len(result) == 0


def test_run_tests_no_tests_selected():
    """Test run_tests when no tests are selected."""
    command = SmartTestCommand()

    args = MagicMock()
    args.all = False
    args.category = None

    categorized_tests = {}

    with patch.object(command, "_select_tests_by_changes", return_value=[]):
        result = command.run_tests(categorized_tests, args)

        assert result["success"] is True
        assert result["tests_run"] == 0


def test_analyze_results_no_output():
    """Test analyze_results with no output."""
    command = SmartTestCommand()

    test_results = {"output": ""}
    result = command.analyze_results(test_results)

    assert "summary" in result
    assert result["summary"] == "No test output to analyze"


@patch("pytest_analyzer.cli.smart_test.SmartTestCommand")
def test_main_function(mock_command_class):
    """Test main function."""
    mock_instance = MagicMock()
    mock_instance.execute.return_value = 0
    mock_command_class.return_value = mock_instance

    result = main()
    assert result == 0
    mock_command_class.assert_called_once()
    mock_instance.execute.assert_called_once()


def test_find_test_files_no_test_dirs(tmp_path):
    """Test _find_test_files when no test directories exist."""
    command = SmartTestCommand()

    # Change to tmp_path directory
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)

        args = MagicMock()
        result = command._find_test_files(args)

        assert isinstance(result, list)
        assert len(result) == 0
    finally:
        os.chdir(original_cwd)
