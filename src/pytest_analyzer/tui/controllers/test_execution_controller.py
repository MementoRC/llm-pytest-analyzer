from typing import TYPE_CHECKING, List, Optional, Tuple

from pytest_analyzer.core.models.pytest_failure import PytestFailure
from pytest_analyzer.tui.controllers.base_controller import BaseController

if TYPE_CHECKING:
    from textual.widgets import Button, Log, ProgressBar

    from pytest_analyzer.tui.app import TUIApp
    from pytest_analyzer.tui.views.test_execution_view import TestExecutionView


class TestExecutionController(BaseController):
    """
    Controller for managing and monitoring test execution in the TUI.
    """

    def __init__(self, app: "TUIApp"):
        super().__init__(app)
        self.analyzer_service = app.analyzer_service
        self._is_executing: bool = False
        self._last_failures: List[PytestFailure] = []
        self.logger.info("TestExecutionController initialized")

    def is_executing(self) -> bool:
        """Returns True if test execution is currently in progress."""
        return self._is_executing

    def get_last_failures(self) -> List[PytestFailure]:
        """Returns the list of PytestFailure objects from the last execution."""
        return self._last_failures.copy()  # Return a copy

    def _get_view_elements(
        self,
    ) -> Optional[Tuple["TestExecutionView", "Log", "ProgressBar", "Button"]]:
        """
        Safely retrieves essential view elements from TestExecutionView.
        Returns None if elements cannot be found.
        """
        try:
            # Ensure TestExecutionView is imported in TYPE_CHECKING
            from textual.widgets import Button, Log, ProgressBar

            from pytest_analyzer.tui.views.test_execution_view import TestExecutionView

            view = self.app.query_one("TestExecutionView", expect_type=TestExecutionView)
            log_widget = view.query_one("#execution_log", expect_type=Log)
            progress_bar = view.query_one("#test_progress_bar", expect_type=ProgressBar)
            run_button = view.query_one("#run_tests_button", expect_type=Button)
            return view, log_widget, progress_bar, run_button
        except Exception as e:
            self.logger.error(f"Failed to get TestExecutionView elements: {e}", exc_info=True)
            return None

    def _update_progress_and_log(
        self,
        message: Optional[str] = None,
        current_progress: Optional[int] = None,
        total_progress: Optional[int] = None,
        progress_visible: Optional[bool] = None,
    ) -> None:
        """Updates the TestExecutionView's log and progress bar."""
        view_elements = self._get_view_elements()
        if not view_elements:
            if message:
                self.logger.warning(f"Could not log (view not found): {message}")
            if any(arg is not None for arg in [current_progress, total_progress, progress_visible]):
                self.logger.warning("Could not update progress bar (view not found).")
            return

        _view, log_widget, progress_bar, _run_button = view_elements

        if message:
            log_widget.write_line(message)

        if progress_visible is not None:
            progress_bar.visible = progress_visible
        if total_progress is not None:
            progress_bar.total = total_progress
        if current_progress is not None:
            progress_bar.progress = current_progress

    async def execute_tests(self, test_path: str, pytest_args: Optional[List[str]] = None) -> None:
        """
        Executes pytest tests using PytestAnalyzerService and updates the TUI.
        """
        if self._is_executing:
            self.logger.warning("Test execution is already in progress.")
            self.app.notify("Test execution is already in progress.", severity="warning")
            return

        self._is_executing = True
        self._last_failures = []  # Clear previous results

        view_elements = self._get_view_elements()
        if not view_elements:
            self.logger.error("Cannot execute tests: TestExecutionView not found or incomplete.")
            self.app.notify("Error: Test execution UI components not found.", severity="error")
            self._is_executing = False
            return

        _view, log_widget, _progress_bar, run_button = view_elements

        run_button.disabled = True
        log_widget.clear()  # Clear log specifically once at the start
        self._update_progress_and_log(
            message="Starting test execution...",
            current_progress=0,
            total_progress=100,
            progress_visible=True,
        )

        try:
            self.logger.info(f"Executing tests for path: {test_path} with args: {pytest_args}")
            effective_pytest_args = pytest_args or []

            failures: List[PytestFailure] = await self.app.run_sync_in_worker(
                self.analyzer_service.run_pytest_only,
                test_path,
                effective_pytest_args,
                quiet=True,
            )
            self._handle_execution_results(failures)

        except Exception as e:
            self.logger.error(f"Error during test execution: {e}", exc_info=True)
            self._update_progress_and_log(
                message=f"[bold red]Error during test execution:[/bold red] {e}",
                current_progress=0,  # Reset progress or show error state
            )
            self.app.notify(f"Test execution failed: {e}", severity="error")
        finally:
            self._is_executing = False
            if view_elements:  # Re-check as it might be None if error was very early
                _view_fin, _log_fin, _prog_fin, run_button_fin = view_elements
                run_button_fin.disabled = False
            # Progress bar remains visible to show final state (100% or error)

    def _handle_execution_results(self, failures: List[PytestFailure]) -> None:
        """
        Processes the results of a test execution and updates UI.
        """
        self._last_failures = failures

        num_total_results = len(failures)
        num_actual_failures = sum(1 for pf in failures if pf.outcome in ["failed", "error"])

        self._update_progress_and_log(
            message=f"Test execution finished. Found {num_total_results} results.",
            current_progress=100,
        )

        if num_actual_failures > 0:
            self._update_progress_and_log(
                message=f"[bold red]Reported {num_actual_failures} failures/errors.[/bold red]"
            )
        else:
            self._update_progress_and_log(
                message="[bold green]All tests passed or were skipped.[/bold green]"
            )

        self.app.notify(f"Test execution complete. {num_actual_failures} failures/errors.")

        # Notify TestResultsController to update its display
        if hasattr(self.app, "test_results_controller") and hasattr(
            self.app.test_results_controller, "load_test_run_results"
        ):
            try:
                # This method needs to exist on TestResultsController
                # It should expect List[PytestFailure]
                self.app.test_results_controller.load_test_run_results(failures)
                self.logger.info("Notified TestResultsController with new execution results.")
            except Exception as e:
                self.logger.error(f"Failed to notify TestResultsController: {e}", exc_info=True)
                self.app.notify("Error updating test results display.", severity="error")
        else:
            self.logger.warning(
                "TestResultsController or its 'load_test_run_results' method not found on app. "
                "Cannot display detailed results from this execution."
            )
            self.app.notify(
                "Could not display detailed test results (controller integration missing).",
                severity="warning",
            )
