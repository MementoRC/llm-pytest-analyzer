import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from pytest_analyzer.core.domain.entities.fix_suggestion import FixSuggestion
from pytest_analyzer.core.domain.entities.pytest_failure import PytestFailure
from pytest_analyzer.core.interfaces.protocols import (
    FailureAnalyzer,
    FixSuggester,
    TestResultRepository,
)


class AnalyzerService:
    """
    Application service facade for analyzing pytest failures and suggesting fixes.

    This service orchestrates the interaction between repositories (for data access),
    analyzers (for understanding failures), and suggesters (for generating fixes).
    It adheres to DDD principles by not containing business logic itself but rather
    coordinating domain services and entities.
    """

    def __init__(
        self,
        repository: TestResultRepository,
        analyzer: FailureAnalyzer,
        suggester: FixSuggester,
    ):
        """
        Initialize the AnalyzerService.

        Args:
            repository: The test result repository for accessing failure data.
            analyzer: The failure analyzer for processing individual failures.
            suggester: The fix suggester for generating repair suggestions.
        """
        self.repository = repository
        self.analyzer = analyzer
        self.suggester = suggester
        self.logger = logging.getLogger(__name__)
        # self.settings: Settings = load_settings() # Uncomment if service needs direct access to settings

    def analyze_report(
        self, report_path: Path, output_path: Optional[Path] = None
    ) -> List[FixSuggestion]:
        """
        Analyze a full pytest report, generate suggestions, and optionally save them.

        Args:
            report_path: Path to the pytest report file (e.g., JSON report).
            output_path: Optional path to save the generated fix suggestions.

        Returns:
            A list of FixSuggestion objects for all processable failures.

        Raises:
            FileNotFoundError: If the report_path does not exist.
            Exception: Can propagate other exceptions from repository access or saving.
        """
        self.logger.info(f"Starting analysis of report: {report_path}")
        all_suggestions: List[FixSuggestion] = []

        try:
            failures = self.repository.get_failures(report_path)
            self.logger.info(f"Loaded {len(failures)} failures from report.")
        except FileNotFoundError:
            self.logger.error(f"Report file not found: {report_path}")
            raise
        except Exception as e:
            self.logger.error(
                f"Error loading failures from report {report_path}: {e}", exc_info=True
            )
            raise

        if not failures:
            self.logger.info("No failures found in the report.")
            return []

        for failure in failures:
            suggestion = self.analyze_single_failure(failure)
            all_suggestions.append(suggestion)

        if output_path:
            try:
                self.repository.save_suggestions(all_suggestions, output_path)
                self.logger.info(
                    f"Successfully saved {len(all_suggestions)} suggestions to {output_path}"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to save suggestions to {output_path}: {e}", exc_info=True
                )
                # Depending on policy, this error could be re-raised or handled.
                # For now, it's logged, and suggestions are still returned.

        self.logger.info(
            f"Analysis of report {report_path} completed. Generated {len(all_suggestions)} suggestions."
        )
        return all_suggestions

    def analyze_single_failure(self, failure: PytestFailure) -> FixSuggestion:
        """
        Analyze a single PytestFailure and generate a FixSuggestion.

        This method encapsulates the logic for analyzing one failure and
        generating a suggestion, including error handling and fallback mechanisms.

        Args:
            failure: The PytestFailure object to analyze.

        Returns:
            A FixSuggestion object. If analysis or suggestion generation fails,
            a fallback suggestion is returned.
        """
        self.logger.debug(
            f"Analyzing single failure: {failure.test_name} (ID: {failure.id})"
        )
        try:
            self.logger.debug(f"Invoking analyzer for failure ID: {failure.id}")
            analysis_results = self.analyzer.analyze(failure)

            self.logger.debug(
                f"Invoking suggester for failure ID: {failure.id} with analysis results."
            )
            suggestion = self.suggester.suggest(failure, analysis_results)

            self.logger.info(f"Generated suggestion for failure ID: {failure.id}")
            return suggestion
        except Exception as e:
            self.logger.error(
                f"Error during analysis or suggestion for failure ID {failure.id} ({failure.test_name}): {e}",
                exc_info=True,
            )
            fallback_suggestion = FixSuggestion.create(
                failure_id=failure.id,
                suggestion_text="Automated suggestion failed.",
                explanation=(
                    f"An unexpected error occurred while trying to generate a suggestion for this failure: {str(e)}. "
                    "Please review the failure details manually."
                ),
            )
            self.logger.warning(
                f"Created fallback suggestion for failure ID: {failure.id}"
            )
            return fallback_suggestion

    def get_failure_summary(self, failures: List[PytestFailure]) -> Dict[str, Any]:
        """
        Generate a summary of the provided list of PytestFailure objects.

        The summary includes total number of failures and a count of failures
        broken down by their type.

        Args:
            failures: A list of PytestFailure objects.

        Returns:
            A dictionary containing summary statistics.
            Example:
            {
                "total_failures": 10,
                "failures_by_type": {
                    "ASSERTION_ERROR": 5,
                    "EXCEPTION": 3,
                    "IMPORT_ERROR": 2
                }
            }
        """
        if not failures:
            return {"total_failures": 0, "failures_by_type": {}}

        self.logger.debug(f"Generating summary for {len(failures)} failures.")
        total_failures = len(failures)

        failure_type_names: List[str] = []
        unknown_type_count = 0
        for failure in failures:
            try:
                if failure.failure_type and hasattr(failure.failure_type, "name"):
                    failure_type_names.append(failure.failure_type.name)
                else:
                    # Handles cases where failure_type is None or an object without 'name'
                    raise AttributeError(
                        "failure_type is None or missing 'name' attribute"
                    )
            except AttributeError as e:
                self.logger.warning(
                    f"Could not determine failure type for failure ID {failure.id} ('{failure.test_name}') "
                    f"due to missing attribute or None type: {e}. Categorizing as UNKNOWN."
                )
                failure_type_names.append("UNKNOWN")
                unknown_type_count += 1

        if unknown_type_count > 0:
            self.logger.warning(
                f"Encountered {unknown_type_count} failures with undetermined types during summary generation. "
                "These have been categorized as UNKNOWN."
            )

        failures_by_type = Counter(failure_type_names)

        summary = {
            "total_failures": total_failures,
            "failures_by_type": dict(failures_by_type),
        }
        self.logger.info(f"Generated failure summary: {summary}")
        return summary
