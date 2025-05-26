from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

# Assuming PytestFailure, TestGroup are available
# (e.g., from gui.models or a core model)
try:
    from pytest_analyzer.core.models import PytestFailure
    from pytest_analyzer.gui.models.test_results_model import TestGroup  # If using this dataclass
except ImportError:
    from dataclasses import dataclass

    # Fallback definitions
    @dataclass
    class PytestFailure:  # Simplified placeholder
        name: str
        # ... other fields

    @dataclass
    class TestGroup:  # Simplified placeholder
        name: str
        tests: List[PytestFailure]


from .base_controller import BaseController

if TYPE_CHECKING:
    from ..app import TUIApp

    # from .test_execution_controller import TestExecutionController # TUI version
    # from ..messages import StatusUpdateMessage, TestSelectedMessage, GroupSelectedMessage


class TestResultsController(BaseController):
    """Manages interactions with test results logic for the TUI."""

    def __init__(self, app: "TUIApp"):
        super().__init__(app)
        self.logger.info("TestResultsControllerTUI initialized")
        self.test_execution_controller: Optional[Any] = (
            None  # Placeholder for TUI TestExecutionController
        )

    def set_test_execution_controller(self, controller: Any) -> None:  # 'Any' for now
        """Set reference to test execution controller."""
        self.test_execution_controller = controller

    async def on_test_selected(self, test: PytestFailure) -> None:
        """Handle test selection from a TUI view."""
        if test:
            self.logger.info(f"Test selected: {test.name}")
            # self.app.post_message(StatusUpdateMessage(f"Selected test: {test.name}"))
            self.app.notify(f"Selected test: {test.name}")
            # Potentially post another message for a details view to update
            # self.app.post_message(TestSelectedMessage(test))
        else:
            self.logger.info("Test selection cleared.")
            # self.app.post_message(StatusUpdateMessage("Test selection cleared."))

    async def on_group_selected(self, group: TestGroup) -> None:
        """Handle group selection from a TUI view."""
        if group:
            num_tests = len(group.tests) if group.tests else 0
            self.logger.info(f"Group selected: {group.name} ({num_tests} tests)")
            # self.app.post_message(StatusUpdateMessage(f"Selected group: {group.name} ({num_tests} tests)"))
            self.app.notify(f"Selected group: {group.name} ({num_tests} tests)")
            # self.app.post_message(GroupSelectedMessage(group))
        else:
            self.logger.info("Group selection cleared.")
            # self.app.post_message(StatusUpdateMessage("Group selection cleared."))

    async def auto_load_test_results(self) -> None:
        """
        Automatically loads test results into the TUI after a test execution completes.
        This would be triggered by a message or call from TestExecutionController.
        """
        if not self.test_execution_controller:
            self.logger.error("No TUI test execution controller reference available.")
            self.app.notify(
                "Error: Cannot load test results (no execution controller).", severity="error"
            )
            return

        # This method's original purpose of pulling results from TestExecutionController
        # is now superseded by TestExecutionController directly calling
        # self.load_test_run_results().
        # If this method is still called from somewhere, it might need to be
        # re-evaluated or removed. For now, just logging its invocation.
        self.logger.info(
            "auto_load_test_results called, but results are now pushed by TestExecutionController."
        )
        self.app.notify(
            "Test results are loaded automatically after execution.", severity="information"
        )
        # Previous logic for pulling and displaying results is removed as it's now handled elsewhere.

    def load_test_run_results(self, failures: List[PytestFailure]) -> None:
        """
        Receives test execution results (failures) from TestExecutionController
        and updates the TUI.
        """
        num_failures = len(failures)
        self.logger.info(f"Received {num_failures} test results/failures from execution.")
        self.app.notify(f"Processing {num_failures} results from test run.")

        # Here, you would typically update a TestResultsView or similar TUI component.
        # This would likely involve posting a message or calling a method on a view object
        # if it were directly accessible. For now, we'll just log and notify.
        # A more robust solution would involve a clear way to update the relevant view,
        # possibly via a message that the view subscribes to.

        self.logger.info(
            "Further TUI updates for test run results would happen in the relevant view."
        )

        if num_failures > 0:
            self.app.notify(
                f"{num_failures} failures/errors reported from run.", severity="warning"
            )
        else:
            self.app.notify("Test run complete, no failures reported.", severity="information")

    def load_report_data(
        self, results: List[PytestFailure], source_path: Path, source_type: str
    ) -> None:
        """
        Called by FileController (or handles a message) to load parsed report data.
        """
        self.logger.info(
            f"Loading {len(results)} results from {source_type} report: {source_path.name}"
        )

        # Update the TUI TestResultsView
        # This requires a way to access the view.
        # Option 1: App has references to main views/widgets
        try:
            # This assumes your MainView or App has a way to get to TestResultsView
            # And TestResultsView is mounted and has an id="test_results_view"
            # And TUIApp has a screen stack, e.g. self.app.screen.query_one(...)
            # This part is highly dependent on your TUI structure.
            # For a direct approach if the view is known:
            # test_results_widget = self.app.query_one("TestResultsView", TestResultsView) # Example
            # test_results_widget.update_results(results)
            self.app.notify(f"Displaying {len(results)} results in TUI (simulated).")

            # For now, let's just log and notify. The actual update would go to the view.
            # The TestResultsView itself might listen for a message.
            # from ..messages import DisplayReportResults
            # self.app.post_message(DisplayReportResults(results, source_path, source_type))

        except Exception as e:
            self.logger.error(f"Failed to update TUI with report data: {e}", exc_info=True)
            self.app.notify("Error displaying report data in TUI.", severity="error")

        status_msg = f"Loaded {len(results)} results from {source_path.name} ({source_type})."
        self.app.notify(status_msg)
