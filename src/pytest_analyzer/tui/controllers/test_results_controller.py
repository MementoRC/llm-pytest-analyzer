from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

from pytest_analyzer.core.models.pytest_failure import PytestFailure

from .base_controller import BaseController

if TYPE_CHECKING:
    from ..app import TUIApp
    from ..views.test_results_view import TestResultsView


class TestResultsController(BaseController):
    """Manages interactions with test results logic for the TUI."""

    def __init__(self, app: "TUIApp"):
        super().__init__(app)
        self.analyzer_service = app.analyzer_service
        self.logger.info("TestResultsControllerTUI initialized")
        self.test_execution_controller: Optional[Any] = None
        self._current_results: List[PytestFailure] = []

    def set_test_execution_controller(self, controller: Any) -> None:
        """Set reference to test execution controller."""
        self.test_execution_controller = controller

    async def on_test_selected(self, test: PytestFailure) -> None:
        """Handle test selection from a TUI view."""
        if test:
            self.logger.info(f"Test selected: {test.test_name}")
            self.app.notify(f"Selected test: {test.test_name}")
            # TODO: In future, show test details in a detail view
        else:
            self.logger.info("Test selection cleared.")

    def _get_test_results_view(self) -> Optional["TestResultsView"]:
        """Get the TestResultsView widget from the app."""
        try:
            from ..views.test_results_view import TestResultsView

            return self.app.query_one("#test_results_view", TestResultsView)
        except Exception as e:
            self.logger.error(f"Could not find TestResultsView: {e}")
            return None

    def load_test_run_results(self, failures: List[PytestFailure]) -> None:
        """
        Receives test execution results (failures) from TestExecutionController
        and updates the TUI.
        """
        num_failures = len(failures)
        self.logger.info(
            f"Received {num_failures} test results/failures from execution."
        )

        # Store the current results
        self._current_results = failures

        # Update the TestResultsView
        test_results_view = self._get_test_results_view()
        if test_results_view:
            test_results_view.update_results(failures)
            self.logger.info(f"Updated TestResultsView with {num_failures} results")
        else:
            self.logger.warning("TestResultsView not available for update")

        # Provide user feedback
        if num_failures > 0:
            self.app.notify(
                f"Test execution complete: {num_failures} failures found",
                severity="warning",
            )
        else:
            self.app.notify(
                "Test execution complete: All tests passed", severity="success"
            )

    def load_results(
        self,
        results: List[PytestFailure],
        source_path: Optional[Path] = None,
        source_type: str = "results",
    ) -> None:
        """
        Public method expected by tests - load test results.
        """
        self.load_report_data(results, source_path or Path("test_results"), source_type)

    def load_report_data(
        self, results: List[PytestFailure], source_path: Path, source_type: str
    ) -> None:
        """
        Called by FileController to load parsed report data from files.
        """
        num_results = len(results)
        self.logger.info(
            f"Loading {num_results} results from {source_type} report: {source_path.name}"
        )

        # Store the current results
        self._current_results = results

        # Update the TestResultsView
        test_results_view = self._get_test_results_view()
        if test_results_view:
            test_results_view.update_results(results)
            self.logger.info(
                f"Updated TestResultsView with {num_results} results from {source_type}"
            )
        else:
            self.logger.warning("TestResultsView not available for update")

        # Provide user feedback
        status_msg = (
            f"Loaded {num_results} results from {source_path.name} ({source_type})"
        )
        self.app.notify(status_msg)

    def get_current_results(self) -> List[PytestFailure]:
        """Get the currently loaded test results."""
        return self._current_results.copy()

    def clear_results(self) -> None:
        """Clear all test results."""
        self._current_results = []
        test_results_view = self._get_test_results_view()
        if test_results_view:
            test_results_view.update_results([])
            self.logger.info("Cleared test results from view")
        self.app.notify("Test results cleared")
