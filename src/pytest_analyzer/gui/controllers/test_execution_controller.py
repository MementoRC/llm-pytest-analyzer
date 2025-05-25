import logging
from typing import TYPE_CHECKING, Any, List, Optional

from PySide6.QtCore import QObject, Signal, Slot

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
    output_received = Signal(str)
    test_execution_completed = Signal(list)  # Emits List[PytestFailure]
    # Signal to emit test counts: passed, failed, skipped, errors
    test_counts_updated = Signal(int, int, int, int)

    def __init__(
        self,
        progress_view: "TestExecutionProgressView",
        output_view: "TestOutputView",  # Added
        task_manager: "TaskManager",
        analyzer_service: "PytestAnalyzerService",  # To access settings like quiet mode
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent, task_manager=task_manager)
        self.logger.debug(
            f"TestExecutionController: Initializing with progress_view: {progress_view}, output_view: {output_view}, task_manager: {task_manager}, analyzer_service: {analyzer_service}"
        )
        self.progress_view = progress_view
        self.output_view = output_view  # Added
        self.analyzer_service = analyzer_service  # For future use, e.g. parsing specific output
        self._current_task_id: Optional[str] = None
        self._cached_failures: List[
            PytestFailure
        ] = []  # Cache for avoiding Qt signal memory issues

        self._connect_signals()
        self.logger.debug("TestExecutionController: Initialization complete.")

    def _connect_signals(self) -> None:
        """Connect signals from TaskManager and ProgressView."""
        self.logger.debug("TestExecutionController: _connect_signals called.")
        if self.task_manager:
            self.logger.debug("TestExecutionController: Connecting TaskManager signals.")
            self.task_manager.task_started.connect(self._handle_task_started)
            self.task_manager.task_progress.connect(self._handle_task_progress)
            self.task_manager.task_completed.connect(self._handle_task_completed)
            self.task_manager.task_failed.connect(self._handle_task_failed)
        else:
            self.logger.debug(
                "TestExecutionController: TaskManager not available, skipping signal connections."
            )

        self.progress_view.cancel_requested.connect(self._handle_cancel_request)
        self.logger.debug("TestExecutionController: Connected progress_view.cancel_requested.")
        self.output_received.connect(self.output_view.append_output)  # Connect signal to view
        self.logger.debug(
            "TestExecutionController: Connected self.output_received to output_view.append_output."
        )
        self.logger.debug("TestExecutionController: _connect_signals finished.")

    def _output_callback_handler(self, text: str) -> None:
        """
        Receives text from the background task (worker thread) and emits it
        via a signal to be handled by the GUI thread.
        """
        # This can be very verbose, so log sparingly or with a summary
        # self.logger.debug(f"TestExecutionController: _output_callback_handler received text (len: {len(text)}). Emitting output_received.")
        self.output_received.emit(text)

    def start_test_run(
        self, test_path: str, pytest_args: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Initiates a test run by submitting a task to the TaskManager.
        """
        self.logger.debug(
            f"TestExecutionController: start_test_run - path: {test_path}, args: {pytest_args}"
        )
        self.logger.info(f"Initiating test run for path: {test_path} with args: {pytest_args}")
        # The actual task submission will happen here, providing the _output_callback_handler
        # This method will be called by MainController.
        effective_pytest_args = pytest_args or []
        task_id = self.submit_background_task(
            callable_task=self.analyzer_service.run_pytest_only,
            args=(test_path, effective_pytest_args),
            kwargs={},  # No additional kwargs needed for now
            use_progress_bridge=True,  # This will pass 'progress' and 'task_id' to run_pytest_only
        )
        self.logger.debug(
            f"TestExecutionController: Submitted background task for run_pytest_only. Task ID: {task_id}"
        )
        self.logger.debug("TestExecutionController: start_test_run finished.")
        return task_id

    def is_test_execution_task(self, task_id: str, description: str) -> bool:
        """Check if the task is a test execution task we should monitor."""
        self.logger.debug(
            f"TestExecutionController: is_test_execution_task - task_id: {task_id}, description: '{description}'"
        )
        # For now, we identify by the description (callable name)
        # This might need to be more robust, e.g., if AnalysisController sets a specific task_id prefix
        is_exec_task = description == TEST_EXECUTION_TASK_DESCRIPTION_PREFIX
        self.logger.debug(f"TestExecutionController: Task is execution task: {is_exec_task}")
        return is_exec_task

    @Slot(str, str)
    def _handle_task_started(self, task_id: str, description: str) -> None:
        """Handle a task starting."""
        self.logger.debug(
            f"TestExecutionController: _handle_task_started - task_id: {task_id}, description: '{description}'"
        )
        if self.is_test_execution_task(task_id, description):
            self.logger.info(
                f"Test execution task '{task_id}' ({description}) started. Showing progress view."
            )

            # Memory monitoring for test execution
            try:
                from PyQt6.QtWidgets import QApplication

                app = QApplication.instance()
                if hasattr(app, "memory_monitor"):
                    app.memory_monitor.log_memory_state(f"TEST_START_{task_id[:8]}")
            except Exception as e:
                self.logger.debug(f"Memory monitoring error: {e}")
            self._current_task_id = task_id
            self.logger.debug(f"TestExecutionController: Set _current_task_id to {task_id}")

            # Force garbage collection before GUI operations to prevent Qt memory issues
            import gc

            gc.collect()
            self.logger.debug("TestExecutionController: Forced garbage collection before GUI start")

            try:
                self.logger.debug(
                    "TestExecutionController: About to call output_view.clear_output()"
                )
                self.output_view.clear_output()  # Clear previous output
                self.logger.debug(
                    "TestExecutionController: Successfully called output_view.clear_output()"
                )

                self.logger.debug(
                    "TestExecutionController: About to call progress_view.reset_view()"
                )
                self.progress_view.reset_view()
                self.logger.debug(
                    "TestExecutionController: Successfully called progress_view.reset_view()"
                )

                self.logger.debug(
                    "TestExecutionController: About to emit test_counts_updated signal"
                )
                self.test_counts_updated.emit(0, 0, 0, 0)  # Reset counts in status bar
                self.logger.debug(
                    "TestExecutionController: Successfully emitted test_counts_updated(0,0,0,0)"
                )

                self.logger.debug("TestExecutionController: About to call progress_view.show()")
                self.progress_view.show()
                self.logger.debug(
                    "TestExecutionController: Successfully called progress_view.show()"
                )

                self.logger.debug(
                    "TestExecutionController: About to call progress_view.update_progress()"
                )
                self.progress_view.update_progress(0, "Running tests...")
                self.logger.debug(
                    "TestExecutionController: Successfully called progress_view.update_progress()"
                )

                self.logger.debug(
                    "TestExecutionController: About to call progress_view.start_timer()"
                )
                self.progress_view.start_timer()
                self.logger.debug(
                    "TestExecutionController: Successfully called progress_view.start_timer()"
                )

            except Exception as e:
                self.logger.error(f"TestExecutionController: Qt operation failed: {e}")
                self.logger.error(f"TestExecutionController: Exception type: {type(e)}")
                import traceback

                self.logger.error(f"TestExecutionController: Traceback: {traceback.format_exc()}")
                raise
        else:
            # If another task starts while one is active, we might want to log or ignore
            if self._current_task_id:
                self.logger.debug(
                    f"TestExecutionController: Another task '{task_id}' ({description}) started while test execution '{self._current_task_id}' is active."
                )
            else:
                self.logger.debug(
                    f"TestExecutionController: Non-test-execution task '{task_id}' ({description}) started. Ignoring in this controller."
                )
        self.logger.debug("TestExecutionController: _handle_task_started finished.")

    @Slot(str, int, str)
    def _handle_task_progress(self, task_id: str, percentage: int, message: str) -> None:
        """Handle progress updates for a task."""
        self.logger.debug(
            f"TestExecutionController: _handle_task_progress - task_id: {task_id}, percentage: {percentage}, message: '{message}'"
        )
        if task_id == self._current_task_id:
            self.logger.debug(
                f"Test execution task '{task_id}' progress: {percentage}% - {message}"
            )
            self.progress_view.update_progress(percentage, message)
            self.logger.debug(
                f"TestExecutionController: Called progress_view.update_progress({percentage}, '{message}')"
            )
            # Future: Parse 'message' for more details like current test if available
        else:
            self.logger.debug(
                f"TestExecutionController: Progress update for non-current task '{task_id}'. Ignoring."
            )
        self.logger.debug("TestExecutionController: _handle_task_progress finished.")

    @Slot(str, object)
    def _handle_task_completed(self, task_id: str, result: Any) -> None:
        """Handle a task completing."""
        self.logger.debug(
            f"TestExecutionController: _handle_task_completed - task_id: {task_id}, result type: {type(result)}"
        )
        if task_id == self._current_task_id:
            # Memory monitoring for test completion
            try:
                from PyQt6.QtWidgets import QApplication

                app = QApplication.instance()
                if hasattr(app, "memory_monitor"):
                    app.memory_monitor.log_memory_state(f"TEST_COMPLETE_{task_id[:8]}")
            except Exception as e:
                self.logger.debug(f"Memory monitoring error: {e}")

            self.logger.info(f"Test execution task '{task_id}' completed.")
            self.progress_view.stop_timer()
            self.logger.debug("TestExecutionController: Called progress_view.stop_timer()")

            final_message = "Test run completed."
            passed_count = 0
            failed_count = 0
            skipped_count = 0  # Pytest plugin does not yet report skipped, but good to have
            error_count = 0
            pytest_failures: List[PytestFailure] = []  # Initialize

            if isinstance(result, list) and (not result or isinstance(result[0], PytestFailure)):
                pytest_failures = result  # Assign to the outer scope variable
                self.logger.debug(
                    f"TestExecutionController: Task result is List[PytestFailure] with {len(pytest_failures)} items."
                )
                # Calculate counts based on outcome
                passed_count = sum(1 for pf in pytest_failures if pf.outcome == "passed")
                failed_count = sum(1 for pf in pytest_failures if pf.outcome == "failed")
                error_count = sum(1 for pf in pytest_failures if pf.outcome == "error")
                skipped_count = sum(1 for pf in pytest_failures if pf.outcome == "skipped")

                final_message = (
                    f"Test run completed. Passed: {passed_count}, Failed: {failed_count}, "
                    f"Errors: {error_count}, Skipped: {skipped_count}."
                )
                self.logger.debug(
                    f"TestExecutionController: Calculated counts - Passed: {passed_count}, Failed: {failed_count}, "
                    f"Errors: {error_count}, Skipped: {skipped_count}"
                )
            else:
                self.logger.warning(
                    f"TestExecutionController: Task result is not List[PytestFailure]. Type: {type(result)}. Cannot determine failure counts accurately."
                )
                # If result is not what's expected, pytest_failures remains an empty list

            # Store failures in the controller instead of passing through signals to avoid Qt memory issues
            self._cached_failures = pytest_failures

            # Emit signal with just the count to avoid Qt memory allocation issues
            self.test_execution_completed.emit(
                []
            )  # Empty list - data accessed via get_last_failures()
            self.logger.debug(
                f"TestExecutionController: Emitted test_execution_completed signal. {len(pytest_failures)} PytestFailure(s) cached."
            )

            # Force memory cleanup before GUI updates
            import gc

            gc.collect()
            gc.collect()  # Double cleanup for more thorough collection
            self.logger.debug("Forced aggressive garbage collection before GUI updates")

            self.progress_view.update_stats(passed_count, failed_count, skipped_count, error_count)
            self.logger.debug(
                f"TestExecutionController: Called progress_view.update_stats with counts P:{passed_count} F:{failed_count} S:{skipped_count} E:{error_count}"
            )
            self.test_counts_updated.emit(passed_count, failed_count, skipped_count, error_count)
            self.logger.debug(
                f"TestExecutionController: Emitted test_counts_updated with P:{passed_count} F:{failed_count} S:{skipped_count} E:{error_count}"
            )
            self.progress_view.update_progress(100, final_message)  # Mark as 100%
            self.logger.debug(
                f"TestExecutionController: Called progress_view.update_progress(100, '{final_message}')"
            )
            # Optionally hide the view after a delay or keep it visible with final stats
            # self.progress_view.hide() # Or a method to set to a "completed" state
            self._current_task_id = None

            # Clear cached failures after GUI updates to prevent accumulation
            self._cached_failures.clear()
            self.logger.debug(
                "TestExecutionController: Cleared _current_task_id and cached failures."
            )
        else:
            self.logger.debug(
                f"TestExecutionController: Task completion for non-current task '{task_id}'. Ignoring."
            )
        self.logger.debug("TestExecutionController: _handle_task_completed finished.")

    @Slot(str, str)
    def _handle_task_failed(self, task_id: str, error_message: str) -> None:
        """Handle a task failing."""
        self.logger.debug(
            f"TestExecutionController: _handle_task_failed - task_id: {task_id}, error: {error_message.splitlines()[0]}"
        )
        if task_id == self._current_task_id:
            self.logger.error(f"Test execution task '{task_id}' failed: {error_message}")
            self.progress_view.stop_timer()
            self.logger.debug("TestExecutionController: Called progress_view.stop_timer()")
            fail_msg = f"Test run failed: {error_message.splitlines()[0]}"
            self.progress_view.update_progress(0, fail_msg)
            self.logger.debug(
                f"TestExecutionController: Called progress_view.update_progress(0, '{fail_msg}')"
            )
            self.test_counts_updated.emit(0, 0, 0, 0)  # Reset counts in status bar on failure
            self.logger.debug(
                "TestExecutionController: Emitted test_counts_updated(0,0,0,0) for failed run."
            )
            # Keep stats as they were, or reset.
            # self.progress_view.hide() # Or set to a "failed" state
            self._current_task_id = None
            self.logger.debug("TestExecutionController: Cleared _current_task_id.")
        else:
            self.logger.debug(
                f"TestExecutionController: Task failure for non-current task '{task_id}'. Ignoring."
            )
        self.logger.debug("TestExecutionController: _handle_task_failed finished.")

    @Slot()
    def _handle_cancel_request(self) -> None:
        """Handle cancel request from the progress view."""
        self.logger.debug("TestExecutionController: _handle_cancel_request called.")
        if self._current_task_id and self.task_manager:
            self.logger.info(f"Cancel requested for test execution task '{self._current_task_id}'.")
            self.task_manager.cancel_task(self._current_task_id)
            self.logger.debug(
                f"TestExecutionController: Called task_manager.cancel_task for task_id: {self._current_task_id}"
            )
            current_progress_val = self.progress_view.progress_bar.value()
            self.progress_view.update_progress(current_progress_val, "Cancellation requested...")
            self.logger.debug(
                f"TestExecutionController: Called progress_view.update_progress({current_progress_val}, 'Cancellation requested...')"
            )
            self.progress_view.stop_timer()  # Stop timer, but view remains until task_failed/completed confirms cancellation
            self.logger.debug("TestExecutionController: Called progress_view.stop_timer()")
            # Button might be disabled by stop_timer, or we can disable it here explicitly.
            self.progress_view.cancel_button.setEnabled(False)
            self.logger.debug("TestExecutionController: Disabled progress_view.cancel_button.")
        else:
            self.logger.debug("TestExecutionController: No current task or task manager to cancel.")
        self.logger.debug("TestExecutionController: _handle_cancel_request finished.")

    def get_last_failures(self) -> List[PytestFailure]:
        """
        Get the cached failures from the last test execution.
        This avoids Qt memory allocation issues when passing large lists through signals.
        """
        return self._cached_failures.copy()  # Return a copy to prevent modification
