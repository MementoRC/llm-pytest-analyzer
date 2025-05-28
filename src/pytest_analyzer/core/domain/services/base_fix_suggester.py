import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pytest_analyzer.core.domain.entities.fix_suggestion import FixSuggestion
from pytest_analyzer.core.domain.entities.pytest_failure import PytestFailure
from pytest_analyzer.core.errors import AnalysisError

logger = logging.getLogger(__name__)


class BaseFixSuggester(ABC):
    """Base class for fix suggesters following DDD principles."""

    def suggest(
        self, failure: PytestFailure, analysis: Optional[Dict[str, Any]] = None
    ) -> FixSuggestion:
        """Suggest a fix for a test failure."""
        try:
            logger.debug(f"Generating fix suggestion for: {failure.test_name}")

            # Common pre-processing logic
            self._validate_failure(failure)
            analysis_data = analysis or {}

            # Generate the actual suggestion (implemented by subclasses)
            suggestion = self._generate_suggestion(failure, analysis_data)

            # Common post-processing logic
            self._validate_suggestion(suggestion)

            logger.debug(f"Fix suggestion generated for: {failure.test_name}")
            return suggestion

        except Exception as e:
            error_msg = (
                f"Failed to generate fix suggestion for '{failure.test_name}': {str(e)}"
            )
            logger.error(error_msg)
            raise AnalysisError(error_msg) from e

    def _validate_failure(self, failure: PytestFailure) -> None:
        """Validate that the failure object is valid for suggestion generation."""
        if not failure.test_name:
            raise AnalysisError("Test failure must have a test name")

        if not failure.failure_message:
            raise AnalysisError("Test failure must have a failure message")

    def _validate_suggestion(self, suggestion: FixSuggestion) -> None:
        """Validate that the generated suggestion is properly formatted."""
        if not isinstance(suggestion, FixSuggestion):
            raise AnalysisError("Generated suggestion must be a FixSuggestion instance")

        if not suggestion.suggestion_text:
            raise AnalysisError("Fix suggestion must have suggestion text")

        if not suggestion.failure_id:
            raise AnalysisError("Fix suggestion must reference a failure ID")

    @abstractmethod
    def _generate_suggestion(
        self, failure: PytestFailure, analysis: Dict[str, Any]
    ) -> FixSuggestion:
        """Generate the actual suggestion (to be implemented by subclasses)."""
        pass
