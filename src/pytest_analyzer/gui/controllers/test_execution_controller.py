import logging
from typing import TYPE_CHECKING, Any, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ...core.models.pytest_failure import PytestFailure
from .base_controller import BaseController

if TYPE_CHECKING:
    from ...core.analyzer_service import PytestAnalyzerService
    from ..background.task_manager import TaskManager
    from ..views.test_execution_progress_view import TestExecutionProgressView
    from ..views.test_output_view import TestOutputView  # Added


logger = logging.getLogger(__name__)

# Define a constant for the task description prefix to identify test execution tasks
TEST_EXECUTION_TASK_DESCRIPTION_PREFIX = "run_pytest_only"  # Matches callable_task.__name__


class TestExecutionController(BaseController):
    """
    Controller for managing and displaying test execution progress.
    Also handles live output from test execution.
    """

    # Signal to emit received output text, to be connected to TestOutputView
    output_received = pyqtSignal(str)

    def __init__(
        self,
        progress_view: "TestExecutionProgressView",
        output_view: "TestOutputView",  # Added
        task_manager: "TaskManager",
        analyzer_service: "PytestAnalyzerService",  # To access settings like quiet mode
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent, task_manager=task_manager)
        self.progress_view = progress_view
        self.output_view = output_view  # Added
        self.analyzer_service = analyzer_service  # For future use, e.g. parsing specific output
        self._current_task_id: Optional[str] = None

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Connect signals from TaskManager and ProgressView."""
        if self.task_manager:
            self.task_manager.task_started.connect(self._handle_task_started)
            self.task_manager.task_progress.connect(self._handle_task_progress)
            self.task_manager.task_completed.connect(self._handle_task_completed)
            self.task_manager.task_failed.connect(self._handle_task_failed)

        self.progress_view.cancel_requested.connect(self._handle_cancel_request)
        self.output_received.connect(self.output_view.append_output)  # Connect signal to view

    def _output_callback_handler(self, text: str) -> None:
        """
        Receives text from the background task (worker thread) and emits it
        via a signal to be handled by the GUI thread.
        """
        self.output_received.emit(text)

    def start_test_run(
        self, test_path: str, pytest_args: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Initiates a test run by submitting a task to the TaskManager.
        """
        self.logger.info(f"Initiating test run for path: {test_path} with args: {pytest_args}")
        # The actual task submission will happen here, providing the _output_callback_handler
        # This method will be called by MainController.
        effective_pytest_args = pytest_args or []
        task_id = self.submit_background_task(
            callable_task=self.analyzer_service.run_pytest_only,
            args=(test_path, effective_pytest_args),
            kwargs={"output_callback": self._output_callback_handler},
            use_progress_bridge=True,  # This will pass 'progress' and 'task_id' to run_pytest_only
        )
        return task_id

    def is_test_execution_task(self, task_id: str, description: str) -> bool:
        """Check if the task is a test execution task we should monitor."""
        # For now, we identify by the description (callable name)
        # This might need to be more robust, e.g., if AnalysisController sets a specific task_id prefix
        return description == TEST_EXECUTION_TASK_DESCRIPTION_PREFIX

    @pyqtSlot(str, str)
    def _handle_task_started(self, task_id: str, description: str) -> None:
        """Handle a task starting."""
        if self.is_test_execution_task(task_id, description):
            self.logger.info(
                f"Test execution task '{task_id}' ({description}) started. Showing progress view."
            )
            self._current_task_id = task_id
            self.output_view.clear_output()  # Clear previous output
            self.progress_view.reset_view()
            self.progress_view.show()
            self.progress_view.update_progress(0, "Running tests...")
            self.progress_view.start_timer()
        else:
            # If another task starts while one is active, we might want to log or ignore
            if self._current_task_id:
                self.logger.debug(
                    f"Another task '{task_id}' ({description}) started while test execution '{self._current_task_id}' is active."
                )

    @pyqtSlot(str, int, str)
    def _handle_task_progress(self, task_id: str, percentage: int, message: str) -> None:
        """Handle progress updates for a task."""
        if task_id == self._current_task_id:
            self.logger.debug(
                f"Test execution task '{task_id}' progress: {percentage}% - {message}"
            )
            self.progress_view.update_progress(percentage, message)
            # Future: Parse 'message' for more details like current test if available

    @pyqtSlot(str, object)
    def _handle_task_completed(self, task_id: str, result: Any) -> None:
        """Handle a task completing."""
        if task_id == self._current_task_id:
            self.logger.info(f"Test execution task '{task_id}' completed.")
            self.progress_view.stop_timer()

            final_message = "Test run completed."
            passed_count = 0
            failed_count = 0
            skipped_count = 0  # Pytest plugin does not yet report skipped, but good to have
            error_count = 0

            if isinstance(result, list) and (not result or isinstance(result[0], PytestFailure)):
                pytest_failures: List[PytestFailure] = result

                # Assuming 'result' is the list of PytestFailure objects from run_pytest_only
                # We don't get total passed/skipped directly from this list.
                # This part needs more info from pytest run if we want accurate passed/skipped.
                # For now, we only count failures/errors from the result.
                for pf in pytest_failures:
                    if pf.error_type == "AssertionError":  # Convention for failures
                        failed_count += 1
                    else:  # Other exceptions are errors
                        error_count += 1

                total_issues = failed_count + error_count
                final_message = f"Test run completed. Found {total_issues} issues ({failed_count} failed, {error_count} errors)."
                # To get passed/skipped, we'd need the pytest summary or a more detailed report object.
                # The current `run_pytest_only` only returns failures.
                # We'll leave passed/skipped as 0 for now.

            self.progress_view.update_stats(passed_count, failed_count, skipped_count, error_count)
            self.progress_view.update_progress(100, final_message)  # Mark as 100%
            # Optionally hide the view after a delay or keep it visible with final stats
            # self.progress_view.hide() # Or a method to set to a "completed" state
            self._current_task_id = None

    @pyqtSlot(str, str)
    def _handle_task_failed(self, task_id: str, error_message: str) -> None:
        """Handle a task failing."""
        if task_id == self._current_task_id:
            self.logger.error(f"Test execution task '{task_id}' failed: {error_message}")
            self.progress_view.stop_timer()
            self.progress_view.update_progress(
                0, f"Test run failed: {error_message.splitlines()[0]}"
            )
            # Keep stats as they were, or reset.
            # self.progress_view.hide() # Or set to a "failed" state
            self._current_task_id = None

    @pyqtSlot()
    def _handle_cancel_request(self) -> None:
        """Handle cancel request from the progress view."""
        if self._current_task_id and self.task_manager:
            self.logger.info(f"Cancel requested for test execution task '{self._current_task_id}'.")
            self.task_manager.cancel_task(self._current_task_id)
            self.progress_view.update_progress(
                self.progress_view.progress_bar.value(), "Cancellation requested..."
            )
            self.progress_view.stop_timer()  # Stop timer, but view remains until task_failed/completed confirms cancellation
            # Button might be disabled by stop_timer, or we can disable it here explicitly.
            self.progress_view.cancel_button.setEnabled(False)
