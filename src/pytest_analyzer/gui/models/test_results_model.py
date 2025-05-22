"""
Test results model for the Pytest Analyzer GUI.

This module contains data models for representing test results in the GUI.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from ...core.models.pytest_failure import FixSuggestion, PytestFailure

# Configure logging
logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Enum representing the status of a test."""

    PASSED = auto()
    FAILED = auto()
    ERROR = auto()
    SKIPPED = auto()
    UNKNOWN = auto()


# Add new Enum AnalysisStatus
class AnalysisStatus(Enum):
    """Enum representing the analysis status of a test failure."""

    NOT_ANALYZED = auto()
    ANALYSIS_PENDING = auto()
    ANALYZED_NO_SUGGESTIONS = auto()
    SUGGESTIONS_AVAILABLE = auto()
    ANALYSIS_FAILED = auto()


@dataclass
class TestFailureDetails:
    """Details of a test failure."""

    message: str = ""
    traceback: str = ""
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    expected: Optional[str] = None
    actual: Optional[str] = None
    error_type: str = ""  # Added field


@dataclass
class TestResult:
    """Class representing a single test result."""

    name: str
    status: TestStatus = TestStatus.UNKNOWN
    duration: float = 0.0
    file_path: Optional[Path] = None
    failure_details: Optional[TestFailureDetails] = None
    suggestions: List[FixSuggestion] = field(default_factory=list)  # Added field
    analysis_status: AnalysisStatus = AnalysisStatus.NOT_ANALYZED  # Added field

    @property
    def is_failed(self) -> bool:
        """Check if the test failed."""
        return self.status == TestStatus.FAILED

    @property
    def is_error(self) -> bool:
        """Check if the test had an error."""
        return self.status == TestStatus.ERROR

    @property
    def short_name(self) -> str:
        """Get the short name of the test (without the module path)."""
        if "::" in self.name:
            return self.name.split("::")[-1]
        return self.name


@dataclass
class TestGroup:
    """Class representing a group of related test failures."""

    name: str
    tests: List[TestResult] = field(default_factory=list)
    root_cause: Optional[str] = None
    suggested_fix: Optional[str] = None


class TestResultsModel(QObject):
    """
    Model for test results data.

    This model holds test results data and provides signals for UI updates.
    """

    # Signals
    results_updated = pyqtSignal()
    groups_updated = pyqtSignal()
    # Add new signals
    suggestions_updated = pyqtSignal(str)  # test_name
    analysis_status_updated = pyqtSignal(str)  # test_name

    def __init__(self):
        """Initialize the test results model."""
        super().__init__()

        self.results: List[TestResult] = []
        self.groups: List[TestGroup] = []
        self.source_file: Optional[Path] = None
        self.source_type: str = ""  # "json", "xml", "py", "output"

    def clear(self) -> None:
        """Clear all test results data."""
        self.results = []
        self.groups = []
        self.source_file = None
        self.source_type = ""

        # Emit signals
        self.results_updated.emit()
        self.groups_updated.emit()

    def set_results(
        self, results: List[TestResult], source_file: Optional[Path], source_type: str
    ) -> None:
        """
        Set test results data.

        Args:
            results: List of test results
            source_file: Source file path
            source_type: Source type
        """
        self.results = results
        self.source_file = source_file
        self.source_type = source_type

        # Emit signal
        self.results_updated.emit()

    def set_groups(self, groups: List[TestGroup]) -> None:
        """
        Set test groups data.

        Args:
            groups: List of test groups
        """
        self.groups = groups

        # Emit signal
        self.groups_updated.emit()

    @property
    def failed_count(self) -> int:
        """Get the number of failed tests."""
        return sum(1 for r in self.results if r.is_failed)

    @property
    def error_count(self) -> int:
        """Get the number of tests with errors."""
        return sum(1 for r in self.results if r.is_error)

    @property
    def total_count(self) -> int:
        """Get the total number of tests."""
        return len(self.results)

    @property
    def group_count(self) -> int:
        """Get the number of test groups."""
        return len(self.groups)

    def update_test_data(
        self,
        test_name: str,
        suggestions: Optional[List[FixSuggestion]] = None,
        analysis_status: Optional[AnalysisStatus] = None,
    ) -> None:
        """
        Update suggestions and/or analysis status for a specific test.
        Emits signals if data was changed.
        """
        found_test = None
        for test_result in self.results:
            if test_result.name == test_name:
                found_test = test_result
                break

        if not found_test:
            logger.warning(f"Test '{test_name}' not found in model for updating data.")
            return

        updated = False
        if suggestions is not None:
            found_test.suggestions = suggestions
            logger.debug(f"Suggestions updated for test '{test_name}'.")
            self.suggestions_updated.emit(test_name)
            updated = True

        if analysis_status is not None:
            if found_test.analysis_status != analysis_status:
                found_test.analysis_status = analysis_status
                logger.debug(
                    f"Analysis status for test '{test_name}' changed to {analysis_status.name}."
                )
                self.analysis_status_updated.emit(test_name)
                updated = True

        if updated:
            # A general signal that views might listen to for redraws
            self.results_updated.emit()

    def get_pytest_failures_for_analysis(self) -> List[PytestFailure]:
        """
        Converts failed or errored TestResult objects to PytestFailure objects
        suitable for analysis.
        """
        pytest_failures: List[PytestFailure] = []
        for tr_result in self.results:
            if tr_result.is_failed or tr_result.is_error:
                if tr_result.failure_details:
                    pf = PytestFailure(
                        test_name=tr_result.name,
                        test_file=str(tr_result.file_path) if tr_result.file_path else "",
                        error_type=tr_result.failure_details.error_type,
                        error_message=tr_result.failure_details.message,
                        traceback=tr_result.failure_details.traceback,
                        line_number=tr_result.failure_details.line_number,
                        # relevant_code and raw_output_section are not stored in TestResult
                    )
                    pytest_failures.append(pf)
                else:
                    logger.warning(
                        f"Test '{tr_result.name}' is marked failed/error but has no failure details. Skipping for analysis."
                    )
        return pytest_failures

    def load_test_run_results(
        self, pytest_failures: List[PytestFailure], source_path: Path, run_source_type: str
    ) -> None:
        """
        Converts PytestFailure objects from a test run into TestResult objects
        and updates the model.
        If pytest_failures is empty, it implies no failures were found.
        """
        test_results: List[TestResult] = []
        if not pytest_failures:
            # If the run produced no failures, we might want to represent this differently,
            # e.g. by showing a "No failures" message or loading all tests with PASSED status
            # if the service could provide that. For now, an empty result list is set.
            logger.info(f"Test run from '{source_path}' reported no failures.")

        for pf_failure in pytest_failures:
            status = TestStatus.ERROR  # Default for errors
            if pf_failure.error_type == "AssertionError":
                status = TestStatus.FAILED

            failure_details = TestFailureDetails(
                message=pf_failure.error_message,
                traceback=pf_failure.traceback,
                file_path=pf_failure.test_file,  # PytestFailure.test_file is the primary file
                line_number=pf_failure.line_number,
                error_type=pf_failure.error_type,
            )

            # PytestFailure.test_file is a string, convert to Path for TestResult.file_path
            test_file_path = Path(pf_failure.test_file) if pf_failure.test_file else None

            tr = TestResult(
                name=pf_failure.test_name,
                status=status,
                duration=0.0,  # PytestFailure doesn't carry duration
                file_path=test_file_path,
                failure_details=failure_details,
                analysis_status=AnalysisStatus.NOT_ANALYZED,  # Reset analysis status for new results
                suggestions=[],  # Reset suggestions
            )
            test_results.append(tr)

        self.set_results(test_results, source_path, run_source_type)
        logger.info(f"Loaded {len(test_results)} results from test run of '{source_path}'.")
