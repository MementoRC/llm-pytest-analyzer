from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal


class WorkflowState(str, Enum):
    """Defines the possible states in the application workflow."""

    IDLE = "idle"  # Initial state, no file/project loaded
    FILE_SELECTED = "file_selected"  # A test file, directory, or report is selected
    TESTS_DISCOVERING = "tests_discovering"  # Test discovery is in progress
    TESTS_DISCOVERED = "tests_discovered"  # Tests have been discovered from a file/directory
    TESTS_RUNNING = "tests_running"  # Tests are currently being executed
    RESULTS_AVAILABLE = "results_available"  # Test results (from run or report) are loaded
    ANALYSIS_RUNNING = "analysis_running"  # LLM analysis is in progress
    FIXES_AVAILABLE = "fixes_available"  # Fix suggestions have been generated
    APPLYING_FIXES = "applying_fixes"  # Fixes are being applied
    FIXES_APPLIED = "fixes_applied"  # Fixes have been successfully applied
    ERROR = "error"  # An error occurred in the workflow

    def __str__(self) -> str:
        return self.value


class WorkflowStateMachine(QObject):
    """Manages the state of the application workflow."""

    state_changed = pyqtSignal(str, str)  # old_state_value, new_state_value
    context_updated = pyqtSignal(dict)  # current_context

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._current_state: WorkflowState = WorkflowState.IDLE
        self._context: Dict[str, Any] = {}

    @property
    def current_state(self) -> WorkflowState:
        """Gets the current workflow state."""
        return self._current_state

    @property
    def context(self) -> Dict[str, Any]:
        """Gets the current workflow context."""
        return self._context

    def transition_to(self, new_state: WorkflowState, **kwargs: Any) -> None:
        """
        Transitions the state machine to a new state and updates context.

        Args:
            new_state: The state to transition to.
            **kwargs: Contextual data to add or update for the new state.
        """
        old_state = self._current_state
        if old_state == new_state and not kwargs:  # No actual change if state and context are same
            return

        self._current_state = new_state
        self._context.update(kwargs)

        # Clean up context items that may not be relevant to the new state
        if new_state == WorkflowState.IDLE:
            self._context.clear()
        elif new_state == WorkflowState.FILE_SELECTED:
            # Keep file_path, file_type, clear others like test_count, failure_count
            relevant_keys = {"file_path", "file_type", "error_message"}
            self._context = {k: v for k, v in self._context.items() if k in relevant_keys}

        self.state_changed.emit(old_state.value, new_state.value)
        self.context_updated.emit(self._context)

    # Convenience transition methods
    def to_idle(self) -> None:
        self.transition_to(WorkflowState.IDLE)

    def to_file_selected(self, file_path: Path, file_type: str) -> None:
        self.transition_to(WorkflowState.FILE_SELECTED, file_path=file_path, file_type=file_type)

    def to_tests_discovering(self) -> None:
        self.transition_to(WorkflowState.TESTS_DISCOVERING)

    def to_tests_discovered(self, test_count: int) -> None:
        self.transition_to(WorkflowState.TESTS_DISCOVERED, test_count=test_count)

    def to_tests_running(self) -> None:
        self.transition_to(WorkflowState.TESTS_RUNNING)

    def to_results_available(self, result_count: int, failure_count: int) -> None:
        self.transition_to(
            WorkflowState.RESULTS_AVAILABLE,
            result_count=result_count,
            failure_count=failure_count,
        )

    def to_analysis_running(self) -> None:
        self.transition_to(WorkflowState.ANALYSIS_RUNNING)

    def to_fixes_available(self, suggestion_count: int) -> None:
        self.transition_to(WorkflowState.FIXES_AVAILABLE, suggestion_count=suggestion_count)

    def to_applying_fixes(self) -> None:
        self.transition_to(WorkflowState.APPLYING_FIXES)

    def to_fixes_applied(self, applied_count: int) -> None:
        self.transition_to(WorkflowState.FIXES_APPLIED, applied_count=applied_count)

    def to_error(self, message: str, previous_state: Optional[WorkflowState] = None) -> None:
        if previous_state is None:
            previous_state = self._current_state
        self.transition_to(
            WorkflowState.ERROR, error_message=message, previous_state=previous_state.value
        )
