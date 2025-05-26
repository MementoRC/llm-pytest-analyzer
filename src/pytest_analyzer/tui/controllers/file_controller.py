from pathlib import Path
from typing import TYPE_CHECKING, Optional

# Assuming TestResult, TestStatus, TestFailureDetails are accessible
# (e.g., from gui.models or a core model)
try:
    from pytest_analyzer.core.models import PytestFailure  # Or your core TestResult type
    from pytest_analyzer.gui.models.test_results_model import (  # If using these dataclasses
        TestFailureDetails,
        TestStatus,
    )

    # If TestResult is QObject-based, you'll need a plain data structure.
    # For this example, let's assume TestResult is a dataclass or similar.
    # If not, define a TUI-specific one or use PytestFailure directly.
    # Let's use PytestFailure as the primary data carrier for parsed results.
except ImportError:
    # Fallback definitions if imports fail (e.g. running TUI standalone without full GUI setup)
    from dataclasses import dataclass
    from enum import Enum

    class TestStatus(Enum):
        PASSED = "PASSED"
        FAILED = "FAILED"
        SKIPPED = "SKIPPED"
        ERROR = "ERROR"
        UNKNOWN = "UNKNOWN"

    @dataclass
    class TestFailureDetails:
        message: str = ""
        traceback: str = ""
        error_type: str = ""

    @dataclass
    class PytestFailure:  # Using this as a generic result structure
        name: str
        status: TestStatus = TestStatus.UNKNOWN
        duration: float = 0.0
        file_path: Optional[Path] = None
        failure_details: Optional[TestFailureDetails] = None
        # Add other fields as necessary, like nodeid, outcome, etc.
        # This should align with what your parsing logic extracts.


from .base_controller import BaseController

if TYPE_CHECKING:
    from ..app import TUIApp

    # If you have specific message types for TUI
    # from ..messages import ReportParsedMessage, StatusUpdateMessage


class FileController(BaseController):
    """Handles file selection, loading, and report parsing for the TUI."""

    # Define a callback type for when a report is parsed, instead of a signal
    # report_parsed_handler: Optional[Callable[[List[PytestFailure], Path, str], None]] = None

    def __init__(self, app: "TUIApp"):
        super().__init__(app)
        self.logger.info("FileControllerTUI initialized")
        # self.test_results_model = app.test_results_model # If TUI has a similar model
        # Or, this controller will directly message other controllers/views

    async def on_path_selected(self, path_str: str) -> None:
        """Handle path selection from the file selection view (or other source)."""
        path = Path(path_str)
        file_type = path.suffix.lower()
        self.logger.info(f"Path selected: {path}, type: {file_type}")

        # Update status bar (example, TUIApp should have a way to show status)
        # self.app.update_status(f"Selected: {path.name}")

        if file_type == ".py":
            await self._load_test_file(path)
        elif path.is_dir():
            await self._load_directory(path)
        elif file_type == ".json":
            await self._load_json_report(path)
        elif file_type == ".xml":
            await self._load_xml_report(path)
        else:
            self.app.notify(f"Unsupported file type: {path.name}", severity="warning")
            self.logger.warning(f"Unsupported file type: {file_type} for path {path.name}")

    async def _load_test_file(self, path: Path) -> None:
        """Prepare for running tests from a specific Python file."""
        self.logger.info(f"Preparing for test file: {path}")
        self.app.current_test_target = path
        self.app.loaded_results = None  # Clear previous results
        # Optionally, trigger discovery here or wait for a separate user action.
        # For now, just setting the target path.
        # Example: await self._discover_tests_in_path(path)
        self.app.notify(
            f"Test file selected: {path.name}. Ready for test operations (e.g., Run, Discover)."
        )

    async def _load_directory(self, path: Path) -> None:
        """Prepare for running tests from a directory."""
        self.logger.info(f"Preparing for test directory: {path}")
        self.app.current_test_target = path
        self.app.loaded_results = None  # Clear previous results
        # Optionally, trigger discovery here.
        # Example: await self._discover_tests_in_path(path)
        self.app.notify(
            f"Directory selected: {path.name}. Ready for test operations (e.g., Run, Discover)."
        )

    async def _load_json_report(self, path: Path) -> None:
        """Load test results from a JSON report file (TUI version)."""
        self.logger.info(f"Loading JSON report: {path}")
        self.app.notify(f"Processing JSON report: {path.name}...")
        try:
            # Use PytestAnalyzerService to parse and analyze the report
            suggestions = await self.app.run_sync_in_worker(
                self.app.analyzer_service.analyze_pytest_output, path
            )
            self.app.loaded_results = suggestions  # Store List[FixSuggestion]
            self.app.current_test_target = path  # Set the report itself as the target

            # Notify app/other controllers about the parsed report
            # The TUI will need to adapt to handle FixSuggestion objects
            num_items = len(suggestions)
            # A suggestion implies a failure, so count suggestions as "issues found"
            status_msg = f"Analyzed {path.name}: Found {num_items} suggestions/issues."

            self.app.notify(status_msg)
            self.logger.info(status_msg)
            # Example: self.app.post_message(ReportAnalyzedMessage(suggestions, path, "json"))

        except Exception as e:
            self.logger.error(f"Error analyzing JSON report {path}: {e}", exc_info=True)
            self.app.notify(f"Error analyzing JSON report: {str(e)}", severity="error")
            self.app.loaded_results = None

    async def _load_xml_report(self, path: Path) -> None:
        """Load test results from an XML report file (TUI version)."""
        self.logger.info(f"Loading XML report: {path}")
        self.app.notify(f"Processing XML report: {path.name}...")
        try:
            # Use PytestAnalyzerService to parse and analyze the report
            suggestions = await self.app.run_sync_in_worker(
                self.app.analyzer_service.analyze_pytest_output, path
            )
            self.app.loaded_results = suggestions  # Store List[FixSuggestion]
            self.app.current_test_target = path  # Set the report itself as the target

            num_items = len(suggestions)
            status_msg = f"Analyzed {path.name}: Found {num_items} suggestions/issues."

            self.app.notify(status_msg)
            self.logger.info(status_msg)
            # Example: self.app.post_message(ReportAnalyzedMessage(suggestions, path, "xml"))

        except Exception as e:
            self.logger.error(f"Error analyzing XML report {path}: {e}", exc_info=True)
            self.app.notify(f"Error analyzing XML report: {str(e)}", severity="error")
            self.app.loaded_results = None

    def _map_test_status(self, status_str: str) -> TestStatus:
        """Map a status string to a TestStatus enum value."""
        status_map = {
            "passed": TestStatus.PASSED,
            "failed": TestStatus.FAILED,
            "error": TestStatus.ERROR,  # For pytest-json-report, "error" might be an outcome
            "skipped": TestStatus.SKIPPED,
            # Add other mappings if necessary (e.g., from JUnit outcomes)
        }
        return status_map.get(status_str.lower(), TestStatus.UNKNOWN)

    # Placeholder for on_report_type_changed if needed in TUI
    # async def on_report_type_changed(self, report_type: str) -> None:
    #     self.logger.info(f"Report type set to: {report_type.upper()}")
    #     self.app.notify(f"Report type set to: {report_type.upper()}")
