"""
Protocol definitions for core components.

This module defines the core protocol interfaces for the pytest-analyzer's
major components: Extractor, Analyzer, Suggester, and Applier.
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from .models.failure_analysis import FailureAnalysis
from .models.pytest_failure import FixSuggestion, PytestFailure


@runtime_checkable
class Extractor(Protocol):
    """
    Protocol for extracting test failures from pytest output.

    Implementations of this protocol are responsible for parsing pytest output
    (in various formats) and extracting structured information about test failures.
    """

    def extract(self, test_results: Any) -> Dict[str, Any]:
        """
        Extract test failures from pytest output.

        Args:
            test_results: The pytest output to extract from (string, path, or structured data)

        Returns:
            A dictionary containing extracted failures and metadata

        Raises:
            ExtractionError: If extraction fails
        """
        ...


@runtime_checkable
class Analyzer(Protocol):
    """
    Protocol for analyzing test failures.

    Implementations of this protocol are responsible for analyzing test failures
    to determine their root causes and patterns.
    """

    def analyze(self, extraction_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze test failures to determine root causes.

        Args:
            extraction_results: Results from an Extractor

        Returns:
            A dictionary containing analysis results

        Raises:
            AnalysisError: If analysis fails
        """
        ...

    def analyze_failure(self, failure: PytestFailure) -> FailureAnalysis:
        """
        Analyze a single test failure.

        Args:
            failure: The test failure to analyze

        Returns:
            Analysis results for the failure

        Raises:
            AnalysisError: If analysis fails
        """
        ...


@runtime_checkable
class Suggester(Protocol):
    """
    Protocol for suggesting fixes for test failures.

    Implementations of this protocol are responsible for generating suggested
    fixes for test failures based on their analysis.
    """

    def suggest(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Suggest fixes for analyzed test failures.

        Args:
            analysis_results: Results from an Analyzer

        Returns:
            A list of suggested fixes

        Raises:
            SuggestionError: If suggestion generation fails
        """
        ...

    def suggest_fix(
        self, failure: PytestFailure, analysis: Optional[FailureAnalysis] = None
    ) -> List[FixSuggestion]:
        """
        Suggest fixes for a specific test failure.

        Args:
            failure: The test failure to suggest fixes for
            analysis: Optional pre-computed analysis

        Returns:
            A list of suggested fixes

        Raises:
            SuggestionError: If suggestion generation fails
        """
        ...


@runtime_checkable
class Applier(Protocol):
    """
    Protocol for applying fixes to code.

    Implementations of this protocol are responsible for applying suggested
    fixes to the codebase and validating the results.
    """

    def apply(
        self, changes: Dict[str, str], validation_tests: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Apply code changes to fix test failures.

        Args:
            changes: Dictionary mapping file paths to new content
            validation_tests: Optional list of tests to run for validation

        Returns:
            Results of the application including success status

        Raises:
            ApplicationError: If application fails
        """
        ...

    def apply_fix_suggestion(self, suggestion: FixSuggestion) -> Dict[str, Any]:
        """
        Apply a specific fix suggestion.

        Args:
            suggestion: The fix suggestion to apply

        Returns:
            Results of the application including success status

        Raises:
            ApplicationError: If application fails
        """
        ...
