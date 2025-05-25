import logging

from PySide6.QtCore import QObject, Signal, Slot

from ..models.test_results_model import TestGroup, TestResult, TestResultsModel
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class TestResultsController(BaseController):
    """Manages interactions with the test results view and model."""

    status_message_updated = Signal(str)

    def __init__(self, test_results_model: TestResultsModel, parent: QObject = None):
        super().__init__(parent)
        self.logger.debug(f"TestResultsController: Initializing with model: {test_results_model}")
        self.test_results_model = test_results_model
        self.test_execution_controller = None  # Will be set by main_controller
        # No direct interaction with TestResultsModel needed here for now,
        # as selection primarily updates details view which is handled by TestResultsView itself.
        # This controller is for reacting to selections if other parts of app need to know.
        self.logger.debug("TestResultsController: Initialization complete.")

    def set_test_execution_controller(self, controller) -> None:
        """Set reference to test execution controller to avoid Qt signal memory issues."""
        self.test_execution_controller = controller

    @Slot(TestResult)
    def on_test_selected(self, test: TestResult) -> None:
        """
        Handle test selection from the test results view.

        Args:
            test: Selected test result
        """
        self.logger.debug(
            f"TestResultsController: on_test_selected - test name: {test.name if test else 'None'}"
        )
        self.status_message_updated.emit(f"Selected test: {test.name}")
        self.logger.debug(
            f"TestResultsController: Emitted status_message_updated with 'Selected test: {test.name}'"
        )
        # Further logic can be added here if other components need to react to test selection.
        self.logger.debug("TestResultsController: on_test_selected finished.")

    @Slot(TestGroup)
    def on_group_selected(self, group: TestGroup) -> None:
        """
        Handle group selection from the test results view.

        Args:
            group: Selected test group
        """
        num_tests = len(group.tests) if group and group.tests else 0
        self.logger.debug(
            f"TestResultsController: on_group_selected - group name: {group.name if group else 'None'}, num_tests: {num_tests}"
        )
        self.status_message_updated.emit(f"Selected group: {group.name} ({len(group.tests)} tests)")
        self.logger.debug(
            f"TestResultsController: Emitted status_message_updated with 'Selected group: {group.name} ({len(group.tests)} tests)'"
        )
        # Further logic for group selection.
        self.logger.debug("TestResultsController: on_group_selected finished.")

    @Slot(list)  # Expects List[PytestFailure]
    def auto_load_test_results(self, ignored_param=None) -> None:
        """
        Automatically loads test results into the model after a test execution completes.
        This slot is connected to TestExecutionController.test_execution_completed.
        Gets failures from controller cache to avoid Qt memory allocation issues.
        """
        if not self.test_execution_controller:
            self.logger.error(
                "TestResultsController: No test execution controller reference available."
            )
            return

        # Get failures from controller cache instead of signal parameter
        pytest_failures = self.test_execution_controller.get_last_failures()
        num_failures = len(pytest_failures)
        self.logger.debug(
            f"TestResultsController: auto_load_test_results called. Retrieved {num_failures} PytestFailure(s) from controller cache."
        )
        self.logger.info(f"Auto-loading {num_failures} test failure(s) from execution.")

        # The source_file and source_type from the model should represent the
        # file/directory that was targeted for the test run.
        executed_path = self.test_results_model.source_file
        original_source_type = self.test_results_model.source_type  # e.g., "py", "directory"
        self.logger.debug(
            f"TestResultsController: Model source_file: {executed_path}, source_type: {original_source_type}"
        )

        if not executed_path:
            self.logger.error(
                "TestResultsController: Cannot auto-load test results: source_file not set in TestResultsModel."
            )
            self.status_message_updated.emit("Error: Could not load test results (source unknown).")
            self.logger.debug("TestResultsController: Emitted status_message_updated with error.")
            return

        # Determine the type of run operation for history tracking
        if original_source_type == "py" or original_source_type == "directory":
            run_operation_type = f"{original_source_type}_run"
        else:
            # Fallback if the source_type is unexpected (e.g., "json", "xml")
            # This case should ideally not happen if "Run Tests" is only enabled for py/directory.
            self.logger.warning(
                f"TestResultsController: Unexpected source_type '{original_source_type}' for test run. Using 'unknown_run'."
            )
            run_operation_type = "unknown_run"
        self.logger.debug(
            f"TestResultsController: Determined run_operation_type: {run_operation_type}"
        )

        self.test_results_model.load_test_run_results(
            pytest_failures, executed_path, run_operation_type
        )
        self.logger.debug(
            f"TestResultsController: Called test_results_model.load_test_run_results with {num_failures} failures, path {executed_path}, type {run_operation_type}."
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
        self.logger.debug(f"TestResultsController: Emitted status_message_updated: {message}")

        # Future: Could call model.compare_with_previous() and pass data to views
        # or emit another signal if specific highlighting updates are needed beyond results_updated.
        # For now, TestResultsView will refresh due to results_updated from the model.
        self.logger.debug("TestResultsController: auto_load_test_results finished.")
