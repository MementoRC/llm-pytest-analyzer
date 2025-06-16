"""
Main service for pytest-analyzer.

This module provides the PytestAnalyzerService, which is the primary entry point
for analyzing pytest test failures and generating fix suggestions.
"""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any, List, Optional

from .core.analysis.llm_suggester import LLMSuggester
from .core.extraction.extractor_factory import get_extractor
from .core.extraction.pytest_plugin import collect_failures_with_plugin
from .core.models.pytest_failure import FixSuggestion, PytestFailure
from .core.orchestration.analyzer_orchestrator import Context, Initialize
from .core.progress.progress_manager import RichProgressManager
from .utils.path_resolver import PathResolver
from .utils.resource_manager import PerformanceTracker
from .utils.settings import Settings, load_settings

logger = logging.getLogger(__name__)


class PytestAnalyzerService:
    """
    Service for analyzing pytest test failures and suggesting fixes.

    This service orchestrates the process of running tests (optional),
    extracting failures from reports, and using various analysis strategies
    (including LLM-based suggestions) to provide actionable feedback.
    """

    def __init__(
        self, settings: Optional[Settings] = None, llm_client: Optional[Any] = None
    ):
        """
        Initializes the PytestAnalyzerService.

        Args:
            settings: Configuration settings. If None, loads from default locations.
            llm_client: An optional pre-configured LLM client instance.
        """
        self.settings = settings or load_settings()
        self.llm_client = llm_client
        self.path_resolver = PathResolver(project_root=self.settings.project_root)
        self.performance_tracker = PerformanceTracker()
        self.progress_manager = RichProgressManager(quiet=False)
        self.llm_suggester = LLMSuggester(
            llm_client=self.llm_client,
            min_confidence=self.settings.min_confidence,
            timeout_seconds=self.settings.llm_timeout,
        )

    def analyze_pytest_output(self, report_path: str) -> List[FixSuggestion]:
        """
        Analyzes a pytest report file to find failures and suggest fixes.

        Args:
            report_path: The path to the pytest report file (e.g., JSON or XML).

        Returns:
            A list of fix suggestions for the identified failures.
        """
        report_file = Path(report_path)
        if not report_file.exists():
            logger.error(f"Report file not found: {report_path}")
            return []

        extractor = get_extractor(report_file, self.settings)
        failures = extractor.extract_failures(report_file)

        if not failures:
            logger.info("No failures found in the report.")
            return []

        return self._get_suggestions(failures)

    def run_and_analyze(self, test_path: str) -> List[FixSuggestion]:
        """
        Runs pytest on a given path and then analyzes the results.

        Args:
            test_path: The path to the tests to run (file or directory).

        Returns:
            A list of fix suggestions for any failures that occurred.
        """
        failures: List[PytestFailure] = []
        if self.settings.preferred_format == "plugin":
            pytest_args = [test_path, "-s", "--disable-warnings"]
            failures = collect_failures_with_plugin(pytest_args)
        else:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=f".{self.settings.preferred_format}",
                delete=False,
                prefix="pytest-analyzer-",
            ) as tmp_report:
                report_path = tmp_report.name

            pytest_args = ["pytest", test_path]
            if self.settings.preferred_format == "json":
                pytest_args.extend(["--json-report", "--json-report-file", report_path])
            elif self.settings.preferred_format == "xml":
                pytest_args.extend([f"--junitxml={report_path}"])

            try:
                subprocess.run(
                    pytest_args,
                    check=False,  # We expect non-zero exit code on failure
                    capture_output=True,
                    text=True,
                    timeout=self.settings.pytest_timeout,
                )
            except subprocess.TimeoutExpired:
                logger.error(
                    f"Pytest execution timed out after {self.settings.pytest_timeout} seconds."
                )
                return []
            except Exception as e:
                logger.error(f"An unexpected error occurred while running pytest: {e}")
                return []

            return self.analyze_pytest_output(report_path)

        if not failures:
            return []

        return self._get_suggestions(failures)

    def _get_suggestions(self, failures: List[PytestFailure]) -> List[FixSuggestion]:
        """
        Orchestrates the suggestion generation process using the state machine.

        Args:
            failures: A list of PytestFailure objects.

        Returns:
            A list of FixSuggestion objects.
        """
        if not self.settings.use_llm:
            logger.info("LLM usage is disabled. Skipping suggestion generation.")
            return []

        context = Context(
            failures=failures,
            quiet=False,
            progress_manager=self.progress_manager,
            path_resolver=self.path_resolver,
            settings=self.settings,
            llm_suggester=self.llm_suggester,
            logger=logger,
            performance_tracker=self.performance_tracker,
        )

        async def run_state_machine():
            await context.transition_to(Initialize)
            await context.execution_complete_event.wait()

        # The RichProgressManager handles the console display
        if self.progress_manager.progress:
            with self.progress_manager.progress:
                asyncio.run(run_state_machine())
        else:
            asyncio.run(run_state_machine())

        if context.final_error:
            logger.error(
                f"Suggestion generation failed with error: {context.final_error}"
            )

        return context.all_suggestions
