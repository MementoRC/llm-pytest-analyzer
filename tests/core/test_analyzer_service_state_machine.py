"""
Tests for the state machine-based analyzer service.

This module contains tests for the analyzer service implementation that uses
a state machine to manage the analysis workflow.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from src.pytest_analyzer.core.analyzer_service_state_machine import (
    StateMachinePytestAnalyzerService,
)
from src.pytest_analyzer.core.analyzer_state_machine import AnalyzerEvent, AnalyzerState
from src.pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure
from src.pytest_analyzer.utils.settings import Settings


@pytest.fixture
def settings():
    """Create a settings object for testing."""
    return Settings(
        max_suggestions=5,
        max_failures=10,
        use_llm=False,
        project_root=os.getcwd(),
    )


@pytest.fixture
def service(settings):
    """Create an analyzer service for testing."""
    return StateMachinePytestAnalyzerService(settings=settings)


@pytest.fixture
def mock_failure():
    """Create a mock test failure."""
    return PytestFailure(
        test_name="test_example",
        test_file="test_file.py",
        error_type="AssertionError",
        error_message="Test failure",
        traceback="Traceback info",
        line_number=10,
    )


@pytest.fixture
def mock_suggestion(mock_failure):
    """Create a mock fix suggestion."""
    return FixSuggestion(
        failure=mock_failure,
        suggestion="Fix suggestion",
        explanation="Explanation of the fix",
        confidence=0.8,
        code_changes={"file_path": "Suggested code changes"},
    )


class TestAnalyzerServiceStateMachine:
    """Test the state machine-based analyzer service implementation."""

    def test_initialization(self, service):
        """Test initialization of the analyzer service."""
        assert service.settings is not None
        assert service.path_resolver is not None
        assert service.state_machine is not None
        assert service.context is not None
        assert service.state_machine.current_state_name == AnalyzerState.INITIALIZING

    @patch("src.pytest_analyzer.core.analyzer_service_state_machine.get_extractor")
    def test_analyze_pytest_output(self, mock_get_extractor, service, mock_failure):
        """Test analyzing pytest output file."""
        # Mock the extractor
        mock_extractor = MagicMock()
        mock_extractor.extract_failures.return_value = [mock_failure]
        mock_get_extractor.return_value = mock_extractor

        # Create a temporary output file
        with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
            # Mock Path.exists to return True
            with patch("pathlib.Path.exists", return_value=True):
                # Also mock _generate_suggestions in the state machine
                with patch.object(
                    service.state_machine, "_generate_suggestions"
                ) as mock_generate:
                    # Make sure we complete the workflow
                    def side_effect():
                        service.context.suggestions = [MagicMock()]
                        service.state_machine.trigger(AnalyzerEvent.COMPLETE)

                    mock_generate.side_effect = side_effect

                    # Analyze the output
                    suggestions = service.analyze_pytest_output(tmp.name)

                    # Verify method calls
                    mock_get_extractor.assert_called_once()
                    mock_extractor.extract_failures.assert_called_once()

                    # Verify state machine transitions
                    assert service.state_machine.is_completed()

                    # Verify suggestions
                    assert len(suggestions) == 1

    @patch("src.pytest_analyzer.core.analyzer_service_state_machine.subprocess.run")
    @patch("src.pytest_analyzer.core.analyzer_service_state_machine.get_extractor")
    def test_run_and_analyze(self, mock_get_extractor, mock_run, service, mock_failure):
        """Test running pytest and analyzing results."""
        # Mock the extractor
        mock_extractor = MagicMock()
        mock_extractor.extract_failures.return_value = [mock_failure]
        mock_get_extractor.return_value = mock_extractor

        # Mock subprocess run
        mock_run.return_value = MagicMock()

        # Patch tempfile to control temporary file names
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            # Mock the temporary file
            mock_temp_file = MagicMock()
            mock_temp_file.name = "/tmp/pytest_output.json"
            mock_temp_file.__enter__.return_value = mock_temp_file
            mock_temp.return_value = mock_temp_file

            # Also mock the progress display
            with patch("rich.progress.Progress") as mock_progress:
                # Mock the progress object
                progress_instance = MagicMock()
                mock_progress.return_value.__enter__.return_value = progress_instance
                progress_instance.add_task.return_value = 1

                # Also mock _generate_suggestions in the state machine
                with patch.object(
                    service.state_machine, "_generate_suggestions"
                ) as mock_generate:
                    # Make sure we complete the workflow
                    def side_effect():
                        service.context.suggestions = [MagicMock()]
                        service.state_machine.trigger(AnalyzerEvent.COMPLETE)

                    mock_generate.side_effect = side_effect

                    # Run and analyze
                    suggestions = service.run_and_analyze(
                        "test_path", ["--quiet"], quiet=True
                    )

                    # Verify method calls
                    mock_run.assert_called()
                    mock_get_extractor.assert_called()
                    mock_extractor.extract_failures.assert_called()

                    # Verify state machine transitions
                    assert service.state_machine.is_completed()

                    # Verify suggestions
                    assert len(suggestions) == 1

    @patch("src.pytest_analyzer.core.analyzer_service_state_machine.subprocess.run")
    @patch("src.pytest_analyzer.core.analyzer_service_state_machine.get_extractor")
    def test_run_pytest_only(self, mock_get_extractor, mock_run, service, mock_failure):
        """Test running pytest without analysis."""
        # Mock the extractor
        mock_extractor = MagicMock()
        mock_extractor.extract_failures.return_value = [mock_failure]
        mock_get_extractor.return_value = mock_extractor

        # Mock subprocess run
        mock_run.return_value = MagicMock()

        # Patch tempfile to control temporary file names
        with patch("tempfile.NamedTemporaryFile") as mock_temp:
            # Mock the temporary file
            mock_temp_file = MagicMock()
            mock_temp_file.name = "/tmp/pytest_output.json"
            mock_temp_file.__enter__.return_value = mock_temp_file
            mock_temp.return_value = mock_temp_file

            # Run pytest only
            failures = service.run_pytest_only("test_path", ["--quiet"], quiet=True)

            # Verify method calls
            mock_run.assert_called()
            mock_get_extractor.assert_called()
            mock_extractor.extract_failures.assert_called()

            # Verify failures
            assert len(failures) == 1
            assert failures[0] == mock_failure

            # State should be ANALYZING after extraction in run_pytest_only
            assert service.state_machine.current_state_name == AnalyzerState.ANALYZING

    def test_apply_suggestion(self, service, mock_suggestion):
        """Test applying a fix suggestion."""
        # Mock the fix applier
        mock_fix_applier = MagicMock()
        mock_result = MagicMock()
        mock_fix_applier.apply_fix_suggestion.return_value = mock_result
        service.context.fix_applier = mock_fix_applier

        # Apply the suggestion
        result = service.apply_suggestion(mock_suggestion)

        # Verify method calls
        mock_fix_applier.apply_fix_suggestion.assert_called_once_with(mock_suggestion)

        # Verify result
        assert result == mock_result

    def test_handle_extraction_error(self, service):
        """Test handling an error during extraction."""
        # Trigger an error
        error = Exception("Test error")
        service.state_machine.set_error(error, "Test error message")

        # Verify error state
        assert service.state_machine.is_error()
        assert service.state_machine.get_error() == error

    def test_no_failures(self, service):
        """Test handling no failures."""
        # Directly set the current state to EXTRACTING
        state_name = AnalyzerState.EXTRACTING
        service.state_machine._current_state = service.state_machine._states[state_name]
        service.state_machine._history = [state_name]

        # Set no failures
        service.context.failures = []

        # Trigger completion
        service.state_machine.trigger(AnalyzerEvent.COMPLETE)

        # Verify completed state
        assert service.state_machine.is_completed()
        assert service.state_machine.get_suggestions() == []

    def test_empty_suggestions(self, service, mock_failure):
        """Test handling no suggestions."""
        # Directly set the current state to SUGGESTING
        state_name = AnalyzerState.SUGGESTING
        service.state_machine._current_state = service.state_machine._states[state_name]
        service.state_machine._history = [state_name]

        # Set failures but no suggestions
        service.context.failures = [mock_failure]
        service.context.suggestions = []

        # Trigger completion
        service.state_machine.trigger(AnalyzerEvent.COMPLETE)

        # Verify completed state
        assert service.state_machine.is_completed()
        assert service.state_machine.get_suggestions() == []
