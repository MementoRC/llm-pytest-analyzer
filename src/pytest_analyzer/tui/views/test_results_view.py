from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label

# Assuming TestResult, TestStatus are available (e.g., from gui.models or a core model)
# from ....gui.models.test_results_model import TestResult, TestStatus
# For now, let's define a placeholder if not available
try:
    from pytest_analyzer.core.models import (
        PytestFailure,  # Or your core TestResult type
    )
    from pytest_analyzer.gui.models.test_results_model import (
        TestStatus,  # If using this enum
    )
except ImportError:
    from dataclasses import dataclass
    from enum import Enum
    from typing import List, Optional

    class TestStatus(Enum):
        PASSED = "PASSED"
        FAILED = "FAILED"
        SKIPPED = "SKIPPED"
        ERROR = "ERROR"
        UNKNOWN = "UNKNOWN"

    @dataclass
    class PytestFailure:  # Simplified placeholder
        name: str
        status: TestStatus = TestStatus.UNKNOWN
        duration: float = 0.0
        message: Optional[str] = None
        traceback: Optional[str] = None


class TestResultsView(Widget):
    """A view for displaying test results."""

    DEFAULT_CSS = """
    TestResultsView {
        layout: vertical;
        overflow-y: auto;
        padding: 1;
        border: round $primary;
        height: auto;
    }
    DataTable {
        height: 1fr;
        margin-top: 1;
    }
    """
    COLUMNS = ["Name", "Status", "Duration (s)", "Message"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._results: List[PytestFailure] = []  # Or your TestResult type

    def compose(self) -> ComposeResult:
        yield Label("Test Results:")
        yield DataTable(id="results_table")

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns(*self.COLUMNS)
        self.update_results([])  # Initial empty state

    def update_results(self, results: List[PytestFailure]) -> None:
        """Update the DataTable with new test results."""
        self._results = results
        table = self.query_one(DataTable)
        table.clear()

        for result in results:
            # Handle outcome properly - it's a string, not an enum
            status_str = str(result.outcome).upper()

            # Handle error message safely
            message_str = result.error_message or ""
            if len(message_str) > 50:  # Truncate long messages for table view
                message_str = message_str[:47] + "..."

            # Use correct field names from PytestFailure model
            table.add_row(
                result.test_name,
                status_str,
                "N/A",  # Duration not available in PytestFailure model
                message_str,
                key=result.test_name,  # Use test_name as unique key
            )

        # Show message if no results
        if not results:
            table.add_row("No results to display.", "", "", "", key="empty")

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle test result row selection."""
        # Skip if this is the empty placeholder row
        if event.row_key.value == "empty":
            return

        # Find the full result based on the key (test_name)
        selected_result = next(
            (r for r in self._results if r.test_name == event.row_key.value), None
        )
        if selected_result:
            self.app.logger.info(f"Test selected: {selected_result.test_name}")
            # Notify with test details
            self.app.notify(
                f"Selected: {selected_result.test_name} - {selected_result.outcome}"
            )

            # If there's a controller, notify it about the selection
            if (
                hasattr(self.app, "test_results_controller")
                and self.app.test_results_controller
            ):
                await self.app.test_results_controller.on_test_selected(selected_result)
