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
from src.pytest_analyzer.core.analyzer_state_machine import (
    AnalyzerContext,
    AnalyzerEvent,
    AnalyzerState,
)
from src.pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure
from src.pytest_analyzer.utils.path_resolver import PathResolver
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
def path_resolver(settings):
    """Create a path resolver for testing."""
    return PathResolver(settings.project_root)


@pytest.fixture
def context(settings, path_resolver):
    """Create an analyzer context for testing."""
    return AnalyzerContext(
        settings=settings,
        path_resolver=path_resolver,
    )


@pytest.fixture
def service(context):
    """Create an analyzer service for testing."""
    return StateMachinePytestAnalyzerService(context=context)


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
        assert service.context is not None
        assert service.context.settings is not None
        assert service.context.path_resolver is not None
        assert service.state_machine is not None
        assert service.state_machine.current_state_name == AnalyzerState.INITIALIZING

    def test_analyze_pytest_output(self, service, mock_failure, mock_suggestion):
        """Test analyzing pytest output file."""
        # Create a temporary file path
        with tempfile.NamedTemporaryFile(suffix=".json") as tmp:
            # Set up mock behavior to bypass file I/O and return mock data
            with patch("pathlib.Path.exists", return_value=True):
                # Prepare the service to return our expected result
                with patch.object(service, "state_machine") as mock_state_machine:
                    # Mock the get_suggestions method to return our mock suggestion
                    mock_state_machine.get_suggestions.return_value = [mock_suggestion]
                    # Mock the is_completed method to return True
                    mock_state_machine.is_completed.return_value = True

                    # Run the method to test
                    result = service.analyze_pytest_output(tmp.name)

                    # Verify results
                    assert len(result) == 1
                    assert result[0] == mock_suggestion

    def test_run_and_analyze(self, service, mock_failure, mock_suggestion):
        """Test running pytest and analyzing results."""
        # Mock the timeout decorator to prevent CI environment issues
        with patch(
            "src.pytest_analyzer.core.analyzer_service_state_machine.with_timeout",
            lambda timeout: lambda func: func,
        ):
            # Set up mocks to bypass UI elements and complex operations
            with patch("rich.progress.Progress"):
                # Mock the state machine to return expected values
                with patch.object(service, "state_machine") as mock_state_machine:
                    # Set up mock state machine behavior
                    mock_state_machine.get_suggestions.return_value = [mock_suggestion]
                    mock_state_machine.is_completed.return_value = True

                    # Mock run_pytest_only to avoid actual test execution
                    with patch.object(service, "run_pytest_only") as mock_run_pytest:
                        mock_run_pytest.return_value = [mock_failure]

                        # Run the method under test (with quiet mode to simplify output)
                        result = service.run_and_analyze(
                            "test_path", ["--quiet"], quiet=True
                        )

                        # Verify the correct results were returned
                        assert len(result) == 1
                        assert result[0] == mock_suggestion

                        # Verify run_pytest_only was called with expected arguments
                        mock_run_pytest.assert_called_once()

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
