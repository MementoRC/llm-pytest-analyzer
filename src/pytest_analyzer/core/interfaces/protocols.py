from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from rich.progress import Progress, TaskID

from ..analysis.fix_applier import FixApplicationResult
from ..domain.entities.fix_suggestion import FixSuggestion
from ..domain.entities.pytest_failure import PytestFailure


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


class PytestRunner(Protocol):
    """Protocol for running pytest tests."""

    def run_tests(
        self,
        test_path: str,
        pytest_args: Optional[List[str]] = None,
        quiet: bool = False,
        progress: Optional[Progress] = None,
        task_id: Optional[TaskID] = None,
    ) -> List[PytestFailure]:
        """Run pytest and return a list of failures."""
        ...


class Applier(Protocol):
    """Protocol for applying code changes."""

    def apply(
        self, code_changes: Dict[str, str], tests_to_validate: List[str]
    ) -> FixApplicationResult:
        """Apply code changes and validate them."""
        ...

    def apply_suggestion(self, suggestion: FixSuggestion) -> FixApplicationResult:
        """Apply a fix suggestion."""
        ...


class Orchestrator(Protocol):
    """Protocol for orchestrating the analysis process."""

    async def generate_suggestions(
        self,
        failures: List[PytestFailure],
        quiet: bool = False,
        progress: Optional[Progress] = None,
        parent_task_id: Optional[TaskID] = None,
    ) -> List[FixSuggestion]:
        """Generate suggestions for a list of failures."""
        ...


class ProgressManager(Protocol):
    """Protocol for managing progress updates."""

    def __init__(
        self,
        progress: Optional[Progress] = None,
        parent_task_id: Optional[TaskID] = None,
        quiet: bool = False,
    ): ...

    def create_task(self, key: str, description: str, **kwargs) -> Optional[TaskID]: ...

    def update_task(
        self,
        key: str,
        description: Optional[str] = None,
        completed: bool = False,
        **kwargs,
    ) -> None: ...

    def cleanup_tasks(self) -> None: ...
