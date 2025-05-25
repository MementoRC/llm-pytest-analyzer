import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from ..models.test_results_model import TestFailureDetails, TestResult, TestResultsModel, TestStatus
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class FileController(BaseController):
    """Handles file selection, loading, and report parsing."""

    python_file_opened = Signal(Path)
    directory_opened = Signal(Path)
    report_parsed = Signal(
        list, Path, str
    )  # results: List[TestResult], source_file: Path, source_type: str (json/xml)
    status_message_updated = Signal(str)

    def __init__(self, test_results_model: TestResultsModel, parent: QObject = None):
        super().__init__(parent)
        self.logger.debug(f"FileController: Initializing with model: {test_results_model}")
        self.test_results_model = test_results_model
        self.logger.debug("FileController: Initialization complete.")

    @Slot(Path)
    def on_file_selected(self, path: Path) -> None:
        """
        Handle file selection from the file selection view.

        Args:
            path: Path to the selected file
        """
        file_type = path.suffix.lower()
        self.logger.debug(
            f"FileController: on_file_selected - path: {path}, determined type: {file_type}"
        )
        self.logger.info(f"File selected: {path}, type: {file_type}")

        if file_type == ".py":
            self.status_message_updated.emit(f"Selected test file: {path.name}")
            self.logger.debug(
                f"FileController: Emitted status_message_updated for Python file: {path.name}"
            )
            self._load_test_file(path)
        elif path.is_dir():  # Check if it's a directory before specific file types
            self.status_message_updated.emit(f"Selected directory: {path.name}")
            self.logger.debug(
                f"FileController: Emitted status_message_updated for directory: {path.name}"
            )
            self._load_directory(path)
        elif file_type == ".json":
            self.status_message_updated.emit(f"Selected JSON report: {path.name}")
            self.logger.debug(
                f"FileController: Emitted status_message_updated for JSON report: {path.name}"
            )
            self._load_json_report(path)
        elif file_type == ".xml":
            self.status_message_updated.emit(f"Selected XML report: {path.name}")
            self.logger.debug(
                f"FileController: Emitted status_message_updated for XML report: {path.name}"
            )
            self._load_xml_report(path)
        else:
            self.status_message_updated.emit(f"Unsupported file type: {path.name}")
            self.logger.warning(
                f"FileController: Unsupported file type: {file_type} for path {path.name}"
            )
            self.logger.debug(
                f"FileController: Emitted status_message_updated for unsupported file type: {path.name}"
            )
        self.logger.debug("FileController: on_file_selected finished.")

    def _load_test_file(self, path: Path) -> None:
        """
        Prepare for running tests from a specific Python file.
        Actual test execution is handled by AnalysisController.on_run_tests.

        Args:
            path: Path to the test file
        """
        self.logger.debug(f"FileController: _load_test_file - path: {path}")
        self.logger.info(f"Preparing for test file: {path}")
        self.test_results_model.clear()  # Clear previous results/source
        self.logger.debug("FileController: Called test_results_model.clear()")
        self.test_results_model.source_file = path
        self.test_results_model.source_type = "py"  # Indicates a single python file as source
        self.logger.debug(
            f"FileController: Set model source_file to {path} and source_type to 'py'"
        )

        self.python_file_opened.emit(path)
        self.logger.debug(f"FileController: Emitted python_file_opened signal with path: {path}")
        status_msg = f"Selected test file: {path.name}. Press 'Refresh Tests' to discover or 'Run Tests' to execute."
        self.status_message_updated.emit(status_msg)
        self.logger.debug(f"FileController: Emitted status_message_updated: {status_msg}")
        self.logger.debug("FileController: _load_test_file finished.")

    def _load_directory(self, path: Path) -> None:
        """
        Prepare for running tests from a directory.
        Actual test execution is handled by AnalysisController.on_run_tests.

        Args:
            path: Path to the directory
        """
        self.logger.debug(f"FileController: _load_directory - path: {path}")
        self.logger.info(f"Preparing for test directory: {path}")
        self.test_results_model.clear()  # Clear previous results/source
        self.logger.debug("FileController: Called test_results_model.clear()")
        self.test_results_model.source_file = path
        self.test_results_model.source_type = "directory"
        self.logger.debug(
            f"FileController: Set model source_file to {path} and source_type to 'directory'"
        )

        self.directory_opened.emit(path)
        self.logger.debug(f"FileController: Emitted directory_opened signal with path: {path}")
        status_msg = f"Selected directory: {path.name}. Press 'Refresh Tests' to discover or 'Run Tests' to execute."
        self.status_message_updated.emit(status_msg)
        self.logger.debug(f"FileController: Emitted status_message_updated: {status_msg}")
        self.logger.debug("FileController: _load_directory finished.")

    def _load_json_report(self, path: Path) -> None:
        """
        Load test results from a JSON report file.

        Args:
            path: Path to the JSON report file
        """
        self.logger.debug(f"FileController: _load_json_report - path: {path}")
        self.logger.info(f"Loading JSON report: {path}")
        try:
            with open(path) as f:
                data = json.load(f)
            self.logger.debug(f"FileController: Successfully loaded JSON data from {path}")

            results: List[TestResult] = []
            if "tests" in data:
                self.logger.debug(
                    f"FileController: Found 'tests' key in JSON data. Processing {len(data['tests'])} items."
                )
                for i, test_data in enumerate(data["tests"]):
                    self.logger.debug(
                        f"FileController: Processing JSON test item {i + 1}: {test_data.get('nodeid', 'Unknown')}"
                    )
                    status = self._map_test_status(test_data.get("outcome", "unknown"))
                    test_result = TestResult(
                        name=test_data.get("nodeid", "Unknown"),
                        status=status,
                        duration=test_data.get("duration", 0.0),
                        file_path=Path(test_data.get("path", "")) if "path" in test_data else None,
                        # Ensure failure_details includes error_type if available from JSON
                    )
                    if test_result.status in (TestStatus.FAILED, TestStatus.ERROR):
                        # Attempt to get error type from JSON if possible (often not standard)
                        # For now, it will remain empty unless JSON has a specific field for it.
                        # Pytest's default JSON report does not provide a distinct 'error_type' field
                        # separate from the 'longrepr' string.
                        failure_details = TestFailureDetails(
                            message=test_data.get("message", ""),
                            traceback=test_data.get("longrepr", ""),
                            error_type="",  # Default to empty as JSON usually doesn't have it
                        )
                        test_result.failure_details = failure_details
                        self.logger.debug(
                            f"FileController: Created TestFailureDetails for {test_result.name}"
                        )
                    results.append(test_result)
            else:
                self.logger.debug("FileController: 'tests' key not found in JSON data.")

            self.report_parsed.emit(results, path, "json")
            self.logger.debug(
                f"FileController: Emitted report_parsed signal with {len(results)} results, path {path}, type 'json'"
            )
            status_msg = f"Loaded {len(results)} test results from {path.name}"
            self.status_message_updated.emit(status_msg)
            self.logger.info(status_msg)
            self.logger.debug(f"FileController: Emitted status_message_updated: {status_msg}")

        except Exception as e:
            self.logger.error(
                f"FileController: Error loading JSON report {path}: {e}", exc_info=True
            )
            QMessageBox.warning(
                None, "Error Loading Report", f"Failed to load JSON report: {str(e)}"
            )
            self.handle_error(f"Error loading JSON report {path}", e)
            status_msg = f"Error loading JSON report: {path.name}"
            self.status_message_updated.emit(status_msg)
            self.logger.debug(
                f"FileController: Emitted status_message_updated with error: {status_msg}"
            )
        self.logger.debug("FileController: _load_json_report finished.")

    def _load_xml_report(self, path: Path) -> None:
        """
        Load test results from an XML report file.

        Args:
            path: Path to the XML report file
        """
        self.logger.debug(f"FileController: _load_xml_report - path: {path}")
        self.logger.info(f"Loading XML report: {path}")
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            self.logger.debug(
                f"FileController: Successfully parsed XML from {path}. Root tag: {root.tag}"
            )
            results: List[TestResult] = []

            if root.tag == "testsuites" or root.tag == "testsuite":
                testsuites = [root] if root.tag == "testsuite" else root.findall("./testsuite")
                self.logger.debug(f"FileController: Found {len(testsuites)} testsuite(s).")
                for ts_idx, testsuite in enumerate(testsuites):
                    self.logger.debug(f"FileController: Processing testsuite {ts_idx + 1}...")
                    for tc_idx, testcase in enumerate(testsuite.findall("./testcase")):
                        name = f"{testcase.get('classname', '')}.{testcase.get('name', '')}"
                        self.logger.debug(
                            f"FileController: Processing testcase {tc_idx + 1}: {name}"
                        )
                        duration = float(testcase.get("time", "0")) if testcase.get("time") else 0.0
                        status = TestStatus.PASSED
                        failure_details = None

                        failure = testcase.find("./failure")
                        error = testcase.find("./error")
                        skipped = testcase.find("./skipped")

                        error_type_str = ""  # Initialize error_type

                        if failure is not None:
                            status = TestStatus.FAILED
                            error_type_str = failure.get(
                                "type", "AssertionError"
                            )  # Junit often has 'type'
                            failure_details = TestFailureDetails(
                                message=failure.get("message", ""),
                                traceback=failure.text or "",
                                error_type=error_type_str,
                            )
                            self.logger.debug(
                                f"FileController: Testcase {name} FAILED. Type: {error_type_str}"
                            )
                        elif error is not None:
                            status = TestStatus.ERROR
                            error_type_str = error.get(
                                "type", "Exception"
                            )  # Junit often has 'type'
                            failure_details = TestFailureDetails(
                                message=error.get("message", ""),
                                traceback=error.text or "",
                                error_type=error_type_str,
                            )
                            self.logger.debug(
                                f"FileController: Testcase {name} ERROR. Type: {error_type_str}"
                            )
                        elif skipped is not None:
                            status = TestStatus.SKIPPED
                            self.logger.debug(f"FileController: Testcase {name} SKIPPED.")
                        else:
                            self.logger.debug(f"FileController: Testcase {name} PASSED.")

                        test_result = TestResult(
                            name=name,
                            status=status,
                            duration=duration,
                            file_path=None,  # XML usually doesn't provide file_path per testcase
                        )
                        if failure_details:
                            test_result.failure_details = failure_details
                        results.append(test_result)
            else:
                self.logger.warning(
                    f"FileController: Unexpected root tag in XML: {root.tag}. Expected 'testsuites' or 'testsuite'."
                )

            self.report_parsed.emit(results, path, "xml")
            self.logger.debug(
                f"FileController: Emitted report_parsed signal with {len(results)} results, path {path}, type 'xml'"
            )
            status_msg = f"Loaded {len(results)} test results from {path.name}"
            self.status_message_updated.emit(status_msg)
            self.logger.info(status_msg)
            self.logger.debug(f"FileController: Emitted status_message_updated: {status_msg}")

        except Exception as e:
            self.logger.error(
                f"FileController: Error loading XML report {path}: {e}", exc_info=True
            )
            QMessageBox.warning(
                None, "Error Loading Report", f"Failed to load XML report: {str(e)}"
            )
            self.handle_error(f"Error loading XML report {path}", e)
            status_msg = f"Error loading XML report: {path.name}"
            self.status_message_updated.emit(status_msg)
            self.logger.debug(
                f"FileController: Emitted status_message_updated with error: {status_msg}"
            )
        self.logger.debug("FileController: _load_xml_report finished.")

    def _map_test_status(self, status_str: str) -> TestStatus:
        """
        Map a status string to a TestStatus enum value.

        Args:
            status_str: Status string

        Returns:
            TestStatus enum value
        """
        self.logger.debug(f"FileController: _map_test_status - input: '{status_str}'")
        status_map = {
            "passed": TestStatus.PASSED,
            "failed": TestStatus.FAILED,
            "error": TestStatus.ERROR,
            "skipped": TestStatus.SKIPPED,
        }
        mapped_status = status_map.get(status_str.lower(), TestStatus.UNKNOWN)
        self.logger.debug(f"FileController: Mapped status '{status_str}' to {mapped_status.name}")
        return mapped_status

    @Slot(str)
    def on_report_type_changed(self, report_type: str) -> None:
        """
        Handle report type change from the file selection view.

        Args:
            report_type: Type of report ('json' or 'xml')
        """
        self.logger.debug(f"FileController: on_report_type_changed - new type: {report_type}")
        # This might be used to pre-configure file dialogs or clear previous selections
        # For now, just logging.
        status_msg = f"Report type set to: {report_type.upper()}"
        self.status_message_updated.emit(status_msg)
        self.logger.debug(f"FileController: Emitted status_message_updated: {status_msg}")
        self.logger.debug("FileController: on_report_type_changed finished.")
