"""
Tests for the analyzer state machine.

This module contains tests for the analyzer state machine implementation,
verifying state transitions, actions, and overall workflow behavior.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.pytest_analyzer.core.analyzer_state_machine import (
    AnalyzerContext,
    AnalyzerEvent,
    AnalyzerState,
    AnalyzerStateMachine,
)
from src.pytest_analyzer.core.models.pytest_failure import FixSuggestion, PytestFailure
from src.pytest_analyzer.utils.path_resolver import PathResolver
from src.pytest_analyzer.utils.settings import Settings


@pytest.fixture
def test_path():
    """Create a test path."""
    return "/path/to/tests"


@pytest.fixture
def output_path():
    """Create a test output path."""
    return Path("/path/to/output.json")


@pytest.fixture
def settings():
    """Create a settings object for testing."""
    return Settings(
        max_suggestions=5,
        max_failures=10,
        use_llm=False,
        project_root="/path/to/project",
    )


@pytest.fixture
def path_resolver(settings):
    """Create a path resolver for testing."""
    return PathResolver(settings.project_root)


@pytest.fixture
def context(settings, path_resolver):
    """Create a test context."""
    return AnalyzerContext(
        settings=settings,
        path_resolver=path_resolver,
    )


@pytest.fixture
def state_machine(context):
    """Create a test state machine."""
    return AnalyzerStateMachine(context)


def create_test_failure(test_name="test_example", status="failed"):
    """Create a test failure for testing."""
    return PytestFailure(
        test_name=test_name,
        status=status,
        message="Test failure",
        traceback="Traceback info",
        test_file="/path/to/test_file.py",
        line_number=10,
    )


def create_fix_suggestion(failure=None, confidence=0.8):
    """Create a fix suggestion for testing."""
    if failure is None:
        failure = create_test_failure()

    return FixSuggestion(
        failure=failure,
        suggestion="Fix suggestion",
        explanation="Explanation of the fix",
        confidence=confidence,
        code_changes={"file_path": "Suggested code changes"},
    )


class TestAnalyzerStateMachine:
    """Test the analyzer state machine implementation."""

    def test_initial_state(self, state_machine):
        """Test that the state machine starts in the initializing state."""
        assert state_machine.current_state_name == AnalyzerState.INITIALIZING

    def test_permitted_triggers_initializing(self, state_machine):
        """Test that the initializing state permits the expected triggers."""
        triggers = state_machine.get_permitted_triggers()
        assert AnalyzerEvent.START_EXTRACTION in triggers
        assert AnalyzerEvent.ERROR in triggers

    @patch("src.pytest_analyzer.core.analyzer_state_machine.FailureAnalyzer")
    @patch("src.pytest_analyzer.core.analyzer_state_machine.FixSuggester")
    @patch("src.pytest_analyzer.core.analyzer_state_machine.FixApplier")
    def test_component_initialization(
        self, mock_fix_applier, mock_fix_suggester, mock_failure_analyzer, state_machine
    ):
        """Test that components are initialized correctly."""
        # Manually call the initializing state's enter action
        state_machine._on_enter_initializing(state_machine.context)

        # Verify that components were initialized
        assert state_machine.context.analyzer is not None
        assert state_machine.context.suggester is not None
        assert state_machine.context.fix_applier is not None

    def test_setup_with_test_path(self, state_machine, test_path):
        """Test setting up the state machine with a test path."""
        state_machine.setup(test_path=test_path)

        assert state_machine.context.test_path == test_path
        # Should have transitioned to extracting state if guard condition is satisfied
        if state_machine._guard_can_extract(state_machine.context, None):
            assert state_machine.current_state_name == AnalyzerState.EXTRACTING

    def test_setup_with_output_path(self, state_machine, output_path):
        """Test setting up the state machine with an output path."""
        with patch("pathlib.Path.exists", return_value=True):
            state_machine.setup(output_path=output_path)

            assert state_machine.context.output_path == output_path
            # Should have transitioned to extracting state if guard condition is satisfied
            if state_machine._guard_can_extract(state_machine.context, None):
                assert state_machine.current_state_name == AnalyzerState.EXTRACTING

    def test_transition_to_analyzing(self, state_machine):
        """Test transitioning from extracting to analyzing state."""
        # Directly set the current state to EXTRACTING
        state_machine._current_state = state_machine._states[AnalyzerState.EXTRACTING]
        state_machine._history = [AnalyzerState.EXTRACTING]

        # Add some test failures
        failure = create_test_failure()
        state_machine.context.failures = [failure]

        # Trigger transition to analyzing state
        result = state_machine.trigger(AnalyzerEvent.START_ANALYSIS)

        assert result.name == "SUCCESS"
        assert state_machine.current_state_name == AnalyzerState.ANALYZING

    def test_transition_to_suggesting(self, state_machine):
        """Test transitioning from analyzing to suggesting state."""
        # Directly set the current state to ANALYZING
        state_machine._current_state = state_machine._states[AnalyzerState.ANALYZING]
        state_machine._history = [AnalyzerState.ANALYZING]

        # Add some test failures
        failure = create_test_failure()
        state_machine.context.failures = [failure]

        # Trigger transition to suggesting state
        result = state_machine.trigger(AnalyzerEvent.START_SUGGESTIONS)

        assert result.name == "SUCCESS"
        assert state_machine.current_state_name == AnalyzerState.SUGGESTING

    def test_transition_to_applying(self, state_machine):
        """Test transitioning from suggesting to applying state."""
        # Directly set the current state to SUGGESTING
        state_machine._current_state = state_machine._states[AnalyzerState.SUGGESTING]
        state_machine._history = [AnalyzerState.SUGGESTING]

        # Add some test suggestions
        failure = create_test_failure()
        suggestion = create_fix_suggestion(failure)
        state_machine.context.suggestions = [suggestion]

        # Trigger transition to applying state
        result = state_machine.trigger(AnalyzerEvent.START_APPLICATION)

        assert result.name == "SUCCESS"
        assert state_machine.current_state_name == AnalyzerState.APPLYING

    def test_transition_to_completed(self, state_machine):
        """Test transitioning to completed state."""
        # Directly set the current state to APPLYING
        state_machine._current_state = state_machine._states[AnalyzerState.APPLYING]
        state_machine._history = [AnalyzerState.APPLYING]

        # Trigger transition to completed state
        result = state_machine.trigger(AnalyzerEvent.COMPLETE)

        assert result.name == "SUCCESS"
        assert state_machine.current_state_name == AnalyzerState.COMPLETED

    def test_transition_to_error(self, state_machine):
        """Test transitioning to error state."""
        # From any state, we should be able to transition to error state
        error = Exception("Test error")
        state_machine.context.error = error
        state_machine.context.error_message = "Test error message"

        # Trigger transition to error state
        result = state_machine.trigger(AnalyzerEvent.ERROR)

        assert result.name == "SUCCESS"
        assert state_machine.current_state_name == AnalyzerState.ERROR

    def test_set_error(self, state_machine):
        """Test setting an error in the state machine."""
        error = Exception("Test error")
        message = "Custom error message"

        # Set the error
        state_machine.set_error(error, message)

        # Verify error state
        assert state_machine.current_state_name == AnalyzerState.ERROR
        assert state_machine.context.error == error
        assert state_machine.context.error_message == message

    def test_guard_can_extract(self, state_machine, test_path, output_path):
        """Test the guard condition for extracting."""
        # Initially false with no paths
        assert not state_machine._guard_can_extract(state_machine.context, None)

        # With test path only
        state_machine.context.test_path = test_path
        assert state_machine._guard_can_extract(state_machine.context, None)

        # With output path only
        state_machine.context.test_path = None
        state_machine.context.output_path = output_path
        assert state_machine._guard_can_extract(state_machine.context, None)

        # With both paths
        state_machine.context.test_path = test_path
        assert state_machine._guard_can_extract(state_machine.context, None)

    def test_guard_has_failures(self, state_machine):
        """Test the guard condition for having failures."""
        # Initially false with no failures
        assert not state_machine._guard_has_failures(state_machine.context, None)

        # With failures
        failure = create_test_failure()
        state_machine.context.failures = [failure]
        assert state_machine._guard_has_failures(state_machine.context, None)

    def test_guard_no_failures(self, state_machine):
        """Test the guard condition for having no failures."""
        # Initially true with no failures
        assert state_machine._guard_no_failures(state_machine.context, None)

        # With failures
        failure = create_test_failure()
        state_machine.context.failures = [failure]
        assert not state_machine._guard_no_failures(state_machine.context, None)

    def test_guard_has_suggestions(self, state_machine):
        """Test the guard condition for having suggestions."""
        # Ensure fix applier exists
        state_machine.context.fix_applier = MagicMock()

        # Initially false with no suggestions
        assert not state_machine._guard_has_suggestions(state_machine.context, None)

        # With suggestions
        suggestion = create_fix_suggestion()
        state_machine.context.suggestions = [suggestion]
        assert state_machine._guard_has_suggestions(state_machine.context, None)

    def test_guard_no_suggestions(self, state_machine):
        """Test the guard condition for having no suggestions."""
        # Initially true with no suggestions
        assert state_machine._guard_no_suggestions(state_machine.context, None)

        # With suggestions
        suggestion = create_fix_suggestion()
        state_machine.context.suggestions = [suggestion]
        assert not state_machine._guard_no_suggestions(state_machine.context, None)

    def test_workflow_failure_to_complete(self, state_machine):
        """Test the entire workflow from extraction to completion with failures."""
        # Set up the context with failures
        failures = [create_test_failure("test_1"), create_test_failure("test_2")]
        state_machine.context.failures = failures

        # Manually step through the state machine
        state_machine.trigger(AnalyzerEvent.START_ANALYSIS)
        assert state_machine.current_state_name == AnalyzerState.ANALYZING

        state_machine.trigger(AnalyzerEvent.START_SUGGESTIONS)
        assert state_machine.current_state_name == AnalyzerState.SUGGESTING

        suggestions = [
            create_fix_suggestion(failures[0]),
            create_fix_suggestion(failures[1]),
        ]
        state_machine.context.suggestions = suggestions

        state_machine.trigger(AnalyzerEvent.START_APPLICATION)
        assert state_machine.current_state_name == AnalyzerState.APPLYING

        state_machine.trigger(AnalyzerEvent.COMPLETE)
        assert state_machine.current_state_name == AnalyzerState.COMPLETED

    def test_workflow_no_failures(self, state_machine):
        """Test the workflow when there are no failures."""
        # No failures in context
        state_machine.context.failures = []

        # Directly set the current state to EXTRACTING
        state_machine._current_state = state_machine._states[AnalyzerState.EXTRACTING]
        state_machine._history = [AnalyzerState.EXTRACTING]

        # Trigger completion
        state_machine.trigger(AnalyzerEvent.COMPLETE)
        assert state_machine.current_state_name == AnalyzerState.COMPLETED

    def test_workflow_no_suggestions(self, state_machine):
        """Test the workflow when there are failures but no suggestions."""
        # Set up the context with failures but no suggestions
        failures = [create_test_failure("test_1"), create_test_failure("test_2")]
        state_machine.context.failures = failures
        state_machine.context.suggestions = []

        # Directly set the current state to SUGGESTING
        state_machine._current_state = state_machine._states[AnalyzerState.SUGGESTING]
        state_machine._history = [AnalyzerState.SUGGESTING]

        # Trigger completion
        state_machine.trigger(AnalyzerEvent.COMPLETE)
        assert state_machine.current_state_name == AnalyzerState.COMPLETED

    def test_reset(self, state_machine):
        """Test resetting the state machine."""
        # First set some context data
        failures = [create_test_failure()]
        suggestions = [create_fix_suggestion()]
        state_machine.context.failures = failures
        state_machine.context.suggestions = suggestions

        # Directly set the current state to COMPLETED
        state_machine._current_state = state_machine._states[AnalyzerState.COMPLETED]
        state_machine._history = [AnalyzerState.COMPLETED]

        # Reset the state machine
        state_machine.trigger(AnalyzerEvent.RESET)

        # Verify state and context
        assert state_machine.current_state_name == AnalyzerState.INITIALIZING
        assert state_machine.context.failures == []
        assert state_machine.context.suggestions == []
        assert state_machine.context.error is None
