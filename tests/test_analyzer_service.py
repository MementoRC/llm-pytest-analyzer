"""Tests for the PytestAnalyzerService."""

import subprocess
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.pytest_analyzer.core.analyzer_service import PytestAnalyzerService
from src.pytest_analyzer.core.models.pytest_failure import PytestFailure
from src.pytest_analyzer.utils.settings import Settings


@pytest.fixture
def test_failure():
    """Create a test failure for testing."""
    return PytestFailure(
        test_name="test_function",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="Traceback...",
        line_number=42,
        relevant_code="def test_function():\n    assert 1 == 2",
    )


@pytest.fixture
def mock_extractor():
    """Create a mock extractor."""
    mock = MagicMock()
    mock.extract_failures.return_value = [
        PytestFailure(
            test_name="test_function",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="assert 1 == 2",
            traceback="Traceback...",
        )
    ]
    return mock


@pytest.fixture
def analyzer_service():
    """Create a PytestAnalyzerService instance."""
    settings = Settings(
        max_failures=10,
        max_suggestions=3,
        min_confidence=0.5,
    )
    return PytestAnalyzerService(settings=settings)


@patch("src.pytest_analyzer.core.analyzer_service.get_extractor")
@patch("src.pytest_analyzer.core.analysis.fix_suggester.FixSuggester.suggest_fixes")
def test_analyze_pytest_output(
    mock_suggest_fixes, mock_get_extractor, mock_extractor, analyzer_service
):
    """Test analyzing pytest output from a file."""
    # Setup
    mock_get_extractor.return_value = mock_extractor
    mock_suggest_fixes.return_value = []  # Mock suggest_fixes to return empty list

    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        # Execute
        with patch("pathlib.Path.exists", return_value=True):
            suggestions = analyzer_service.analyze_pytest_output(tmp.name)

        # Assert
        mock_get_extractor.assert_called_once()
        mock_extractor.extract_failures.assert_called_once()
        mock_suggest_fixes.assert_called()
        assert len(suggestions) == 0  # No suggestions since we mocked the suggester


@patch("src.pytest_analyzer.core.extraction.extractor_factory.get_extractor")
def test_analyze_pytest_output_nonexistent_file(mock_get_extractor, analyzer_service):
    """Test analyzing a nonexistent pytest output file."""
    # Execute
    with patch("pathlib.Path.exists", return_value=False):
        suggestions = analyzer_service.analyze_pytest_output("nonexistent_file.json")

    # Assert
    mock_get_extractor.assert_not_called()
    assert len(suggestions) == 0


@patch("src.pytest_analyzer.core.analyzer_service.collect_failures_with_plugin")
@patch("src.pytest_analyzer.core.analysis.fix_suggester.FixSuggester.suggest_fixes")
def test_run_and_analyze_plugin(mock_suggest_fixes, mock_collect, analyzer_service):
    """Test running and analyzing tests with plugin integration."""
    # Setup
    mock_collect.return_value = [
        PytestFailure(
            test_name="test_function",
            test_file="test_file.py",
            error_type="AssertionError",
            error_message="assert 1 == 2",
            traceback="Traceback...",
        )
    ]
    mock_suggest_fixes.return_value = []  # Mock suggest_fixes to return empty list

    analyzer_service.settings.preferred_format = "plugin"

    # Execute
    suggestions = analyzer_service.run_and_analyze("test_path")

    # Assert
    # Expect the call with additional flags added by the service
    mock_collect.assert_called_once_with(["test_path", "-s", "--disable-warnings"])
    mock_suggest_fixes.assert_called()
    assert len(suggestions) == 0  # No suggestions since we mocked the suggester


@patch("subprocess.run")
@patch("src.pytest_analyzer.core.analyzer_service.get_extractor")
@patch("src.pytest_analyzer.core.analysis.fix_suggester.FixSuggester.suggest_fixes")
def test_run_and_analyze_json(
    mock_suggest_fixes, mock_get_extractor, mock_run, mock_extractor, analyzer_service
):
    """Test running and analyzing tests with JSON output."""
    # Setup
    mock_get_extractor.return_value = mock_extractor
    mock_suggest_fixes.return_value = []  # Mock suggest_fixes to return empty list

    analyzer_service.settings.preferred_format = "json"

    # Execute
    with patch("tempfile.NamedTemporaryFile"):
        suggestions = analyzer_service.run_and_analyze("test_path")

    # Assert
    mock_run.assert_called_once()
    mock_get_extractor.assert_called_once()
    mock_extractor.extract_failures.assert_called_once()
    mock_suggest_fixes.assert_called()
    assert len(suggestions) == 0  # No suggestions since we mocked the suggester


@patch("subprocess.run")
@patch("src.pytest_analyzer.core.analyzer_service.get_extractor")
@patch("src.pytest_analyzer.core.analysis.fix_suggester.FixSuggester.suggest_fixes")
def test_run_and_analyze_xml(
    mock_suggest_fixes, mock_get_extractor, mock_run, mock_extractor, analyzer_service
):
    """Test running and analyzing tests with XML output."""
    # Setup
    mock_get_extractor.return_value = mock_extractor
    mock_suggest_fixes.return_value = []  # Mock suggest_fixes to return empty list

    analyzer_service.settings.preferred_format = "xml"

    # Execute
    with patch("tempfile.NamedTemporaryFile"):
        suggestions = analyzer_service.run_and_analyze("test_path")

    # Assert
    mock_run.assert_called_once()
    mock_get_extractor.assert_called_once()
    mock_extractor.extract_failures.assert_called_once()
    mock_suggest_fixes.assert_called()
    assert len(suggestions) == 0  # No suggestions since we mocked the suggester


@patch("subprocess.run")
def test_run_and_analyze_timeout(mock_run, analyzer_service):
    """Test handling a timeout when running pytest."""
    # Setup
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)

    # Execute
    suggestions = analyzer_service.run_and_analyze("test_path")

    # Assert
    mock_run.assert_called_once()
    assert len(suggestions) == 0
