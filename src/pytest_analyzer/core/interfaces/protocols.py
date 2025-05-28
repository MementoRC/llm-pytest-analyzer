from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from pytest_analyzer.core.domain.entities.fix_suggestion import FixSuggestion
from pytest_analyzer.core.domain.entities.pytest_failure import PytestFailure


class FailureAnalyzer(Protocol):
    """Protocol for analyzing test failures."""

    def analyze(self, failure: PytestFailure) -> Dict[str, Any]:
        """Analyze a test failure and return analysis results."""
        ...


class FixSuggester(Protocol):
    """Protocol for suggesting fixes for test failures."""

    def suggest(
        self, failure: PytestFailure, analysis: Optional[Dict[str, Any]] = None
    ) -> FixSuggestion:
        """Suggest a fix for a test failure."""
        ...


class TestResultRepository(Protocol):
    """Protocol for accessing test results."""

    def get_failures(self, report_path: Path) -> List[PytestFailure]:
        """Get all failures from a test report."""
        ...

    def save_suggestions(
        self, suggestions: List[FixSuggestion], output_path: Path
    ) -> None:
        """Save fix suggestions to an output file."""
        ...
