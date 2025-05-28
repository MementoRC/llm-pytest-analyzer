import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from pytest_analyzer.core.domain.entities.pytest_failure import PytestFailure
from pytest_analyzer.core.errors import AnalysisError

logger = logging.getLogger(__name__)


class BaseFailureAnalyzer(ABC):
    """Base class for failure analyzers following DDD principles."""

    def analyze(self, failure: PytestFailure) -> Dict[str, Any]:
        """Analyze a test failure and return analysis results."""
        try:
            logger.debug(f"Analyzing test failure: {failure.test_name}")

            # Common pre-processing logic
            self._validate_failure(failure)

            # Perform the actual analysis (implemented by subclasses)
            result = self._perform_analysis(failure)

            # Common post-processing logic
            self._validate_analysis_result(result)

            logger.debug(f"Analysis completed for: {failure.test_name}")
            return result

        except Exception as e:
            error_msg = (
                f"Failed to analyze test failure '{failure.test_name}': {str(e)}"
            )
            logger.error(error_msg)
            raise AnalysisError(error_msg) from e

    def _validate_failure(self, failure: PytestFailure) -> None:
        """Validate that the failure object is valid for analysis."""
        if not failure.test_name:
            raise AnalysisError("Test failure must have a test name")

        if not failure.failure_message:
            raise AnalysisError("Test failure must have a failure message")

    def _validate_analysis_result(self, result: Dict[str, Any]) -> None:
        """Validate that the analysis result is properly formatted."""
        if not isinstance(result, dict):
            raise AnalysisError("Analysis result must be a dictionary")

    @abstractmethod
    def _perform_analysis(self, failure: PytestFailure) -> Dict[str, Any]:
        """Perform the actual analysis (to be implemented by subclasses)."""
        pass
