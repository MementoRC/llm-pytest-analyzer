import logging
from typing import List

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ...core.models.pytest_failure import PytestFailure
from ..models.test_results_model import TestGroup, TestResult, TestResultsModel
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class TestResultsController(BaseController):
    """Manages interactions with the test results view and model."""

    status_message_updated = pyqtSignal(str)

    def __init__(self, test_results_model: TestResultsModel, parent: QObject = None):
        super().__init__(parent)
        self.test_results_model = test_results_model
        # No direct interaction with TestResultsModel needed here for now,
        # as selection primarily updates details view which is handled by TestResultsView itself.
        # This controller is for reacting to selections if other parts of app need to know.

    @pyqtSlot(TestResult)
    def on_test_selected(self, test: TestResult) -> None:
        """
        Handle test selection from the test results view.

        Args:
            test: Selected test result
        """
        self.logger.debug(f"Test selected: {test.name}")
        self.status_message_updated.emit(f"Selected test: {test.name}")
        # Further logic can be added here if other components need to react to test selection.

    @pyqtSlot(TestGroup)
    def on_group_selected(self, group: TestGroup) -> None:
        """
        Handle group selection from the test results view.

        Args:
            group: Selected test group
        """
        self.logger.debug(f"Group selected: {group.name}")
        self.status_message_updated.emit(f"Selected group: {group.name} ({len(group.tests)} tests)")
        # Further logic for group selection.

    @pyqtSlot(list)  # Expects List[PytestFailure]
    def auto_load_test_results(self, pytest_failures: List[PytestFailure]) -> None:
        """
        Automatically loads test results into the model after a test execution completes.
        This slot is connected to TestExecutionController.test_execution_completed.

        Args:
            pytest_failures: A list of PytestFailure objects from the test run.
        """
        num_failures = len(pytest_failures)
        self.logger.info(f"Auto-loading {num_failures} test failure(s) from execution.")

        # The source_file and source_type from the model should represent the
        # file/directory that was targeted for the test run.
        executed_path = self.test_results_model.source_file
        original_source_type = self.test_results_model.source_type  # e.g., "py", "directory"

        if not executed_path:
            self.logger.error(
                "Cannot auto-load test results: source_file not set in TestResultsModel."
            )
            self.status_message_updated.emit("Error: Could not load test results (source unknown).")
            return

        # Determine the type of run operation for history tracking
        if original_source_type == "py" or original_source_type == "directory":
            run_operation_type = f"{original_source_type}_run"
        else:
            # Fallback if the source_type is unexpected (e.g., "json", "xml")
            # This case should ideally not happen if "Run Tests" is only enabled for py/directory.
            self.logger.warning(
                f"Unexpected source_type '{original_source_type}' for test run. Using 'unknown_run'."
            )
            run_operation_type = "unknown_run"

        self.test_results_model.load_test_run_results(
            pytest_failures, executed_path, run_operation_type
        )

        if num_failures == 0:
            message = f"Test run completed for '{executed_path.name}'. No failures reported."
        elif num_failures == 1:
            message = f"Test run completed for '{executed_path.name}'. 1 failure reported."
        else:
            message = (
                f"Test run completed for '{executed_path.name}'. {num_failures} failures reported."
            )

        self.status_message_updated.emit(message)
        self.logger.info(message)

        # Future: Could call model.compare_with_previous() and pass data to views
        # or emit another signal if specific highlighting updates are needed beyond results_updated.
        # For now, TestResultsView will refresh due to results_updated from the model.
