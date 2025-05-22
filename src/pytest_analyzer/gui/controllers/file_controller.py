import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from ..models.test_results_model import TestFailureDetails, TestResult, TestResultsModel, TestStatus
from .base_controller import BaseController

logger = logging.getLogger(__name__)


class FileController(BaseController):
    """Handles file selection, loading, and report parsing."""

    results_loaded = pyqtSignal(
        list, Path, str
    )  # results: List[TestResult], source_file: Path, source_type: str
    status_message_updated = pyqtSignal(str)

    def __init__(self, test_results_model: TestResultsModel, parent: QObject = None):
        super().__init__(parent)
        self.test_results_model = test_results_model

    @pyqtSlot(Path)
    def on_file_selected(self, path: Path) -> None:
        """
        Handle file selection from the file selection view.

        Args:
            path: Path to the selected file
        """
        file_type = path.suffix.lower()
        self.logger.info(f"File selected: {path}, type: {file_type}")

        if file_type == ".py":
            self.status_message_updated.emit(f"Selected test file: {path.name}")
            self._load_test_file(path)
        elif file_type == ".json":
            self.status_message_updated.emit(f"Selected JSON report: {path.name}")
            self._load_json_report(path)
        elif file_type == ".xml":
            self.status_message_updated.emit(f"Selected XML report: {path.name}")
            self._load_xml_report(path)
        else:
            self.status_message_updated.emit(f"Unsupported file type: {path.name}")
            self.logger.warning(f"Unsupported file type: {file_type}")

    def _load_test_file(self, path: Path) -> None:
        """
        Load test file for analysis. (Placeholder)

        Args:
            path: Path to the test file
        """
        self.logger.info(f"Loading test file: {path}")
        # This would typically run the tests in the file
        # For now, just show a message
        QMessageBox.information(
            None,  # Parent widget, None for now
            "Test File",
            f"Running tests in {path.name} will be implemented in a future task.",
        )
        # Clear existing results
        self.test_results_model.clear()
        self.status_message_updated.emit(f"Test file {path.name} selected (run not implemented).")

    def _load_json_report(self, path: Path) -> None:
        """
        Load test results from a JSON report file.

        Args:
            path: Path to the JSON report file
        """
        self.logger.info(f"Loading JSON report: {path}")
        try:
            with open(path) as f:
                data = json.load(f)

            results: List[TestResult] = []
            if "tests" in data:
                for test_data in data["tests"]:
                    test_result = TestResult(
                        name=test_data.get("nodeid", "Unknown"),
                        status=self._map_test_status(test_data.get("outcome", "unknown")),
                        duration=test_data.get("duration", 0.0),
                        file_path=Path(test_data.get("path", "")) if "path" in test_data else None,
                    )
                    if test_result.status in (TestStatus.FAILED, TestStatus.ERROR):
                        failure_details = TestFailureDetails(
                            message=test_data.get("message", ""),
                            traceback=test_data.get("longrepr", ""),
                        )
                        test_result.failure_details = failure_details
                    results.append(test_result)

            self.results_loaded.emit(results, path, "json")
            self.status_message_updated.emit(f"Loaded {len(results)} test results from {path.name}")
            self.logger.info(f"Loaded {len(results)} test results from {path}")

        except Exception as e:
            QMessageBox.warning(
                None, "Error Loading Report", f"Failed to load JSON report: {str(e)}"
            )
            self.handle_error(f"Error loading JSON report {path}", e)
            self.status_message_updated.emit(f"Error loading JSON report: {path.name}")

    def _load_xml_report(self, path: Path) -> None:
        """
        Load test results from an XML report file.

        Args:
            path: Path to the XML report file
        """
        self.logger.info(f"Loading XML report: {path}")
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            results: List[TestResult] = []

            if root.tag == "testsuites" or root.tag == "testsuite":
                testsuites = [root] if root.tag == "testsuite" else root.findall("./testsuite")
                for testsuite in testsuites:
                    for testcase in testsuite.findall("./testcase"):
                        name = f"{testcase.get('classname', '')}.{testcase.get('name', '')}"
                        duration = float(testcase.get("time", "0")) if testcase.get("time") else 0.0
                        status = TestStatus.PASSED
                        failure_details = None

                        failure = testcase.find("./failure")
                        error = testcase.find("./error")
                        skipped = testcase.find("./skipped")

                        if failure is not None:
                            status = TestStatus.FAILED
                            failure_details = TestFailureDetails(
                                message=failure.get("message", ""),
                                traceback=failure.text or "",
                            )
                        elif error is not None:
                            status = TestStatus.ERROR
                            failure_details = TestFailureDetails(
                                message=error.get("message", ""),
                                traceback=error.text or "",
                            )
                        elif skipped is not None:
                            status = TestStatus.SKIPPED

                        test_result = TestResult(
                            name=name, status=status, duration=duration, file_path=None
                        )
                        if failure_details:
                            test_result.failure_details = failure_details
                        results.append(test_result)

            self.results_loaded.emit(results, path, "xml")
            self.status_message_updated.emit(f"Loaded {len(results)} test results from {path.name}")
            self.logger.info(f"Loaded {len(results)} test results from {path}")

        except Exception as e:
            QMessageBox.warning(
                None, "Error Loading Report", f"Failed to load XML report: {str(e)}"
            )
            self.handle_error(f"Error loading XML report {path}", e)
            self.status_message_updated.emit(f"Error loading XML report: {path.name}")

    def _map_test_status(self, status_str: str) -> TestStatus:
        """
        Map a status string to a TestStatus enum value.

        Args:
            status_str: Status string

        Returns:
            TestStatus enum value
        """
        status_map = {
            "passed": TestStatus.PASSED,
            "failed": TestStatus.FAILED,
            "error": TestStatus.ERROR,
            "skipped": TestStatus.SKIPPED,
        }
        return status_map.get(status_str.lower(), TestStatus.UNKNOWN)

    @pyqtSlot(str)
    def on_report_type_changed(self, report_type: str) -> None:
        """
        Handle report type change from the file selection view.

        Args:
            report_type: Type of report ('json' or 'xml')
        """
        self.logger.debug(f"Report type changed to {report_type}")
        # This might be used to pre-configure file dialogs or clear previous selections
        # For now, just logging.
        self.status_message_updated.emit(f"Report type set to: {report_type.upper()}")
