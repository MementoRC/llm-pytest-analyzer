import logging
from typing import List

from ...utils.resource_manager import with_timeout
from ..models.pytest_failure import FixSuggestion, PytestFailure
from .error_strategies import (
    AssertionErrorStrategy,
    AttributeErrorStrategy,
    ErrorAnalysisStrategy,
    GenericErrorStrategy,
    ImportErrorStrategy,
    IndexErrorStrategy,
    KeyErrorStrategy,
    NameErrorStrategy,
    SyntaxErrorStrategy,
    TypeErrorStrategy,
    ValueErrorStrategy,
)

logger = logging.getLogger(__name__)


class FailureAnalyzer:
    """
    Analyzes test failures and suggests fixes using the Strategy pattern.

    This class delegates error-type-specific analysis to strategy classes,
    reducing code duplication and improving maintainability.
    """

    def __init__(self, max_suggestions: int = 3):
        """
        Initialize the failure analyzer.

        Args:
            max_suggestions: Maximum number of suggestions per failure
        """
        self.max_suggestions = max_suggestions
        self._init_strategies()

    def _init_strategies(self):
        """Initialize error analysis strategies for each error type."""
        self.error_strategies: dict[str, ErrorAnalysisStrategy] = {
            "AssertionError": AssertionErrorStrategy(),
            "AttributeError": AttributeErrorStrategy(),
            "ImportError": ImportErrorStrategy(),
            "TypeError": TypeErrorStrategy(),
            "NameError": NameErrorStrategy(),
            "IndexError": IndexErrorStrategy(),
            "KeyError": KeyErrorStrategy(),
            "ValueError": ValueErrorStrategy(),
            "SyntaxError": SyntaxErrorStrategy(),
        }
        self.generic_strategy = GenericErrorStrategy()

    @with_timeout(60)
    def analyze_failure(self, failure: PytestFailure) -> List[FixSuggestion]:
        """
        Analyze a test failure and suggest fixes.

        Args:
            failure: PytestFailure object to analyze

        Returns:
            List of suggested fixes
        """
        try:
            base_error_type = self._get_base_error_type(failure.error_type)
            strategy = self.error_strategies.get(base_error_type, self.generic_strategy)
            suggestions = strategy.analyze(failure)
            return suggestions[: self.max_suggestions]
        except Exception as e:
            logger.error(f"Error analyzing failure: {e}")
            return []

    def _get_base_error_type(self, error_type: str) -> str:
        """
        Extract the base error type from a potentially qualified name.

        Args:
            error_type: Error type string

        Returns:
            Base error type (e.g., 'AssertionError' from 'unittest.AssertionError')
        """
        if "." in error_type:
            return error_type.split(".")[-1]
        return error_type
