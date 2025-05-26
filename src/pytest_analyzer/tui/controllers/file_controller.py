import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Optional

# Assuming TestResult, TestStatus, TestFailureDetails are accessible
# (e.g., from gui.models or a core model)
try:
    from pytest_analyzer.core.models import PytestFailure # Or your core TestResult type
    from pytest_analyzer.gui.models.test_results_model import ( # If using these dataclasses
        TestFailureDetails,
        TestResult, # This might be PySide dependent if it inherits QObject
        TestStatus,
    )
    # If TestResult is QObject-based, you'll need a plain data structure.
    # For this example, let's assume TestResult is a dataclass or similar.
    # If not, define a TUI-specific one or use PytestFailure directly.
    # Let's use PytestFailure as the primary data carrier for parsed results.
except ImportError:
    # Fallback definitions if imports fail (e.g. running TUI standalone without full GUI setup)
    from dataclasses import dataclass, field
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
    class PytestFailure: # Using this as a generic result structure
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
        # In TUI, this might mean setting state in PytestAnalyzerService or a TUI model
        # self.app.analyzer_service.set_target_path(path, "py")
        self.app.notify(f"Test file selected: {path.name}. Ready to run tests.")
        # Example: Post a message or update a TUI model/state
        # self.app.post_message(StatusUpdateMessage(f"Selected test file: {path.name}"))
        # self.app.post_message(PythonFileOpenedMessage(path))

    async def _load_directory(self, path: Path) -> None:
        """Prepare for running tests from a directory."""
        self.logger.info(f"Preparing for test directory: {path}")
        # self.app.analyzer_service.set_target_path(path, "directory")
        self.app.notify(f"Directory selected: {path.name}. Ready to run tests.")

    async def _load_json_report(self, path: Path) -> None:
        """Load test results from a JSON report file (TUI version)."""
        self.logger.info(f"Loading JSON report: {path}")
        try:
            # Run synchronous file I/O and parsing in a worker thread
            results = await self.app.run_sync_in_worker(self._parse_json_report_sync, path)

            # Notify app/other controllers about the parsed report
            # This could be a Textual message or a direct call to another controller
            # Example: self.app.main_controller.test_results_controller.load_report_data(results, path, "json")
            # Or: from ..messages import ReportParsed
            #     self.app.post_message(ReportParsed(results, path, "json"))

            status_msg = f"Loaded {len(results)} test results from {path.name}"
            self.app.notify(status_msg)
            self.logger.info(status_msg)

        except Exception as e:
            self.logger.error(f"Error loading JSON report {path}: {e}", exc_info=True)
            self.app.notify(f"Error loading JSON report: {str(e)}", severity="error")

    def _parse_json_report_sync(self, path: Path) -> List[PytestFailure]:
        """Synchronous part of JSON parsing, suitable for run_sync_in_worker."""
        with open(path) as f:
            data = json.load(f)
        
        parsed_results: List[PytestFailure] = []
        if "tests" in data:
            for test_data in data["tests"]:
                status_str = test_data.get("outcome", "unknown")
                status = self._map_test_status(status_str)
                
                failure_details = None
                if status in (TestStatus.FAILED, TestStatus.ERROR):
                    failure_details = TestFailureDetails(
                        message=test_data.get("message", ""), # Pytest JSON report might not have 'message'
                        traceback=test_data.get("longrepr", ""),
                        error_type="", # JSON report usually doesn't provide this directly
                    )

                # Assuming PytestFailure is the target structure
                result_item = PytestFailure(
                    name=test_data.get("nodeid", "Unknown Test"),
                    status=status,
                    duration=test_data.get("duration", 0.0),
                    file_path=Path(test_data.get("path", "")) if "path" in test_data else None,
                    failure_details=failure_details
                )
                parsed_results.append(result_item)
        return parsed_results


    async def _load_xml_report(self, path: Path) -> None:
        """Load test results from an XML report file (TUI version)."""
        self.logger.info(f"Loading XML report: {path}")
        try:
            results = await self.app.run_sync_in_worker(self._parse_xml_report_sync, path)
            
            # Notify app/other controllers
            # Example: self.app.main_controller.test_results_controller.load_report_data(results, path, "xml")
            # Or: self.app.post_message(ReportParsed(results, path, "xml"))

            status_msg = f"Loaded {len(results)} test results from {path.name}"
            self.app.notify(status_msg)
            self.logger.info(status_msg)

        except Exception as e:
            self.logger.error(f"Error loading XML report {path}: {e}", exc_info=True)
            self.app.notify(f"Error loading XML report: {str(e)}", severity="error")

    def _parse_xml_report_sync(self, path: Path) -> List[PytestFailure]:
        """Synchronous part of XML parsing."""
        tree = ET.parse(path)
        root = tree.getroot()
        parsed_results: List[PytestFailure] = []

        for testcase in root.findall(".//testcase"): # JUnit format
            name = f"{testcase.get('classname', '')}.{testcase.get('name', '')}"
            duration = float(testcase.get("time", "0"))
            status = TestStatus.PASSED
            failure_details = None
            error_type_str = ""

            failure = testcase.find("./failure")
            error = testcase.find("./error")
            skipped = testcase.find("./skipped")

            if failure is not None:
                status = TestStatus.FAILED
                error_type_str = failure.get("type", "AssertionError")
                failure_details = TestFailureDetails(
                    message=failure.get("message", ""),
                    traceback=failure.text or "",
                    error_type=error_type_str,
                )
            elif error is not None:
                status = TestStatus.ERROR
                error_type_str = error.get("type", "Exception")
                failure_details = TestFailureDetails(
                    message=error.get("message", ""),
                    traceback=error.text or "",
                    error_type=error_type_str,
                )
            elif skipped is not None:
                status = TestStatus.SKIPPED
            
            result_item = PytestFailure(
                name=name,
                status=status,
                duration=duration,
                # XML usually doesn't provide file_path per testcase easily
                file_path=None, 
                failure_details=failure_details
            )
            parsed_results.append(result_item)
        return parsed_results

    def _map_test_status(self, status_str: str) -> TestStatus:
        """Map a status string to a TestStatus enum value."""
        status_map = {
            "passed": TestStatus.PASSED,
            "failed": TestStatus.FAILED,
            "error": TestStatus.ERROR, # For pytest-json-report, "error" might be an outcome
            "skipped": TestStatus.SKIPPED,
            # Add other mappings if necessary (e.g., from JUnit outcomes)
        }
        return status_map.get(status_str.lower(), TestStatus.UNKNOWN)

    # Placeholder for on_report_type_changed if needed in TUI
    # async def on_report_type_changed(self, report_type: str) -> None:
    #     self.logger.info(f"Report type set to: {report_type.upper()}")
    #     self.app.notify(f"Report type set to: {report_type.upper()}")
