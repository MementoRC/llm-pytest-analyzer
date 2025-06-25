"""Tests for the PytestAnalyzerService."""

import subprocess
import tempfile
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pytest_analyzer.analyzer_service import PytestAnalyzerService
from pytest_analyzer.core.models.pytest_failure import PytestFailure
from pytest_analyzer.utils.settings import Settings


@pytest.fixture
def test_failure():
    """Create a test failure for testing."""
    failure = PytestFailure(
        test_name="test_function",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="assert 1 == 2",
        traceback="Traceback...",
        line_number=42,
        relevant_code="def test_function():\n    assert 1 == 2",
    )
    # The orchestrator expects an 'id' on the failure object.
    failure.id = str(uuid.uuid4())
    return failure


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
        use_llm=True,  # Enable LLM for tests
    )
    return PytestAnalyzerService(settings=settings)


@patch("pytest_analyzer.analyzer_service.get_extractor")
def test_analyze_pytest_output(mock_get_extractor, mock_extractor, analyzer_service):
    """Test analyzing pytest output from a file."""
    # Setup
    mock_get_extractor.return_value = mock_extractor
    # Mock the async LLM suggester to return empty suggestions
    analyzer_service.llm_suggester.batch_suggest_fixes = AsyncMock(return_value={})

    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        # Execute - let the async state machine run normally
        with patch("pathlib.Path.exists", return_value=True):
            suggestions = analyzer_service.analyze_pytest_output(tmp.name)

        # Assert
        mock_get_extractor.assert_called_once()
        mock_extractor.extract_failures.assert_called_once()
        # The suggester's async method should be awaited (since we let asyncio.run execute)
        analyzer_service.llm_suggester.batch_suggest_fixes.assert_awaited()
        assert len(suggestions) == 0  # No suggestions since we mocked an empty response


@patch("pytest_analyzer.analyzer_service.get_extractor")
def test_analyze_pytest_output_nonexistent_file(mock_get_extractor, analyzer_service):
    """Test analyzing a nonexistent pytest output file."""
    # Execute
    with patch("pathlib.Path.exists", return_value=False):
        suggestions = analyzer_service.analyze_pytest_output("nonexistent_file.json")

    # Assert
    mock_get_extractor.assert_not_called()
    assert len(suggestions) == 0


@patch("pytest_analyzer.analyzer_service.collect_failures_with_plugin")
def test_run_and_analyze_plugin(mock_collect, analyzer_service, test_failure):
    """Test running and analyzing tests with plugin integration."""
    # Setup
    mock_collect.return_value = [test_failure]
    analyzer_service.llm_suggester.batch_suggest_fixes = AsyncMock(return_value={})
    analyzer_service.settings.preferred_format = "plugin"

    # Execute
    suggestions = analyzer_service.run_and_analyze("test_path")

    # Assert
    mock_collect.assert_called_once_with(["test_path", "-s", "--disable-warnings"])
    analyzer_service.llm_suggester.batch_suggest_fixes.assert_awaited()
    assert len(suggestions) == 0


@patch("subprocess.run")
@patch("pytest_analyzer.analyzer_service.get_extractor")
def test_run_and_analyze_json(
    mock_get_extractor, mock_run, mock_extractor, analyzer_service
):
    """Test running and analyzing tests with JSON output."""
    # Setup
    mock_get_extractor.return_value = mock_extractor
    analyzer_service.llm_suggester.batch_suggest_fixes = AsyncMock(return_value={})
    analyzer_service.settings.preferred_format = "json"

    # Execute - properly mock tempfile to return a real filename
    with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = tmp.name
            with patch("pathlib.Path.exists", return_value=True):
                suggestions = analyzer_service.run_and_analyze("test_path")

    # Assert
    mock_run.assert_called_once()
    mock_get_extractor.assert_called_once()
    mock_extractor.extract_failures.assert_called_once()
    analyzer_service.llm_suggester.batch_suggest_fixes.assert_awaited()
    assert len(suggestions) == 0


@patch("subprocess.run")
@patch("pytest_analyzer.analyzer_service.get_extractor")
def test_run_and_analyze_xml(
    mock_get_extractor, mock_run, mock_extractor, analyzer_service
):
    """Test running and analyzing tests with XML output."""
    # Setup
    mock_get_extractor.return_value = mock_extractor
    analyzer_service.llm_suggester.batch_suggest_fixes = AsyncMock(return_value={})
    analyzer_service.settings.preferred_format = "xml"

    # Execute - properly mock tempfile to return a real filename
    with tempfile.NamedTemporaryFile(suffix=".xml") as tmp:
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = tmp.name
            with patch("pathlib.Path.exists", return_value=True):
                suggestions = analyzer_service.run_and_analyze("test_path")

    # Assert
    mock_run.assert_called_once()
    mock_get_extractor.assert_called_once()
    mock_extractor.extract_failures.assert_called_once()
    analyzer_service.llm_suggester.batch_suggest_fixes.assert_awaited()
    assert len(suggestions) == 0


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
