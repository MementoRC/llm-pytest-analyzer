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

# Configure logging
logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Enum representing the status of a test."""

    PASSED = auto()
    FAILED = auto()
    ERROR = auto()
    SKIPPED = auto()
    UNKNOWN = auto()


@dataclass
class TestFailureDetails:
    """Details of a test failure."""

    message: str = ""
    traceback: str = ""
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    expected: Optional[str] = None
    actual: Optional[str] = None


@dataclass
class TestResult:
    """Class representing a single test result."""

    name: str
    status: TestStatus = TestStatus.UNKNOWN
    duration: float = 0.0
    file_path: Optional[Path] = None
    failure_details: Optional[TestFailureDetails] = None

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
