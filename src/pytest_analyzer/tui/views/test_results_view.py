from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import DataTable, Label

# Assuming TestResult, TestStatus are available (e.g., from gui.models or a core model)
# from ....gui.models.test_results_model import TestResult, TestStatus
# For now, let's define a placeholder if not available
try:
    from pytest_analyzer.core.models import PytestFailure  # Or your core TestResult type
    from pytest_analyzer.gui.models.test_results_model import TestStatus  # If using this enum
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
        self._results = results
        table = self.query_one(DataTable)
        table.clear()
        for result in results:
            status_str = (
                result.status.value if hasattr(result.status, "value") else str(result.status)
            )
            message_str = result.message or ""
            if len(message_str) > 50:  # Truncate long messages for table view
                message_str = message_str[:47] + "..."

            table.add_row(
                result.name,
                status_str,
                f"{result.duration:.4f}",
                message_str,
                key=result.name,  # Assuming name is unique for key
            )
        if not results:
            table.add_row("No results to display.", "", "", "")

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # Find the full result based on the key (name)
        selected_result = next((r for r in self._results if r.name == event.row_key.value), None)
        if selected_result:
            self.app.logger.info(f"Test selected: {selected_result.name}")
            # Post message for details view or other actions
            # from ..messages import TestSelected
            # self.post_message(TestSelected(selected_result))
            # For now, just notify
            self.app.notify(f"Selected: {selected_result.name} - {selected_result.status}")
