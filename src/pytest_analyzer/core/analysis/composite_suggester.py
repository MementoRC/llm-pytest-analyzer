"""
Composite suggester for combining multiple suggestion strategies.

This module provides a composite implementation of the Suggester protocol
that combines suggestions from multiple suggestion strategies (rule-based,
LLM-based, etc.) and prioritizes them based on confidence scores.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from ..models.failure_analysis import FailureAnalysis
from ..models.pytest_failure import FixSuggestion, PytestFailure
from ..protocols import Suggester

logger = logging.getLogger(__name__)


class CompositeSuggester(Suggester):
    """
    A suggester that combines multiple suggestion strategies.

    This class implements the Suggester protocol and delegates to multiple
    underlying suggester implementations, combining their results and
    removing duplicates.
    """

    def __init__(
        self,
        suggesters: List[Suggester],
        min_confidence: float = 0.5,
        max_suggestions_per_failure: int = 3,
        deduplicate: bool = True,
    ):
        """
        Initialize the composite suggester.

        Args:
            suggesters: List of suggester implementations to delegate to
            min_confidence: Minimum confidence threshold for suggestions
            max_suggestions_per_failure: Maximum number of suggestions per failure
            deduplicate: Whether to deduplicate suggestions
        """
        self.suggesters = suggesters
        self.min_confidence = min_confidence
        self.max_suggestions_per_failure = max_suggestions_per_failure
        self.deduplicate = deduplicate

    def suggest(self, analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Suggest fixes for analyzed test failures by combining results from all suggesters.

        Args:
            analysis_results: Results from an Analyzer

        Returns:
            A list of suggested fixes as dictionaries

        Raises:
            SuggestionError: If suggestion generation fails for all suggesters
        """
        all_suggestions = []

        # Collect suggestions from all suggesters
        for suggester in self.suggesters:
            try:
                suggestions = suggester.suggest(analysis_results)
                all_suggestions.extend(suggestions)
            except Exception as e:
                logger.error(f"Error from suggester {type(suggester).__name__}: {e}")
                # Continue with other suggesters if one fails

        # Group suggestions by failure
        grouped_suggestions = self._group_suggestions_by_failure(all_suggestions)

        # Flatten and return
        result = []
        for failure_key, suggestions in grouped_suggestions.items():
            result.extend(suggestions)

        return result

    def suggest_fix(
        self, failure: PytestFailure, analysis: Optional[FailureAnalysis] = None
    ) -> List[FixSuggestion]:
        """
        Suggest fixes for a specific test failure using all available suggesters.

        Args:
            failure: The test failure to suggest fixes for
            analysis: Optional pre-computed analysis

        Returns:
            A list of suggested fixes

        Raises:
            SuggestionError: If suggestion generation fails for all suggesters
        """
        all_suggestions = []

        # Collect suggestions from all suggesters
        for suggester in self.suggesters:
            try:
                suggestions = suggester.suggest_fix(failure, analysis)
                all_suggestions.extend(suggestions)
            except Exception as e:
                logger.error(f"Error from suggester {type(suggester).__name__}: {e}")
                # Continue with other suggesters if one fails

        # Filter, deduplicate and limit
        return self._process_suggestions(all_suggestions, failure.test_name)

    def _group_suggestions_by_failure(
        self, suggestions: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group suggestions by failure and process each group.

        Args:
            suggestions: List of suggestion dictionaries

        Returns:
            Dictionary mapping failure identifiers to processed suggestion lists
        """
        # Group by failure identifier
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for suggestion in suggestions:
            failure = suggestion.get("failure", {})
            test_name = failure.get("test_name", "unknown")

            if test_name not in grouped:
                grouped[test_name] = []

            grouped[test_name].append(suggestion)

        # Process each group (filter, deduplicate, limit)
        for test_name, group in grouped.items():
            # Filter by confidence
            filtered = [s for s in group if s.get("confidence", 0) >= self.min_confidence]

            # Deduplicate if enabled
            if self.deduplicate:
                filtered = self._deduplicate_dict_suggestions(filtered)

            # Sort by confidence (descending)
            filtered.sort(key=lambda s: s.get("confidence", 0), reverse=True)

            # Limit number of suggestions per failure
            if self.max_suggestions_per_failure > 0:
                filtered = filtered[: self.max_suggestions_per_failure]

            # Update the group
            grouped[test_name] = filtered

        return grouped

    def _process_suggestions(
        self, suggestions: List[FixSuggestion], test_name: str
    ) -> List[FixSuggestion]:
        """
        Process a list of suggestions for a single failure.

        Args:
            suggestions: List of suggestions to process
            test_name: Name of the test for logging purposes

        Returns:
            Processed list of suggestions
        """
        # Filter by confidence
        filtered = [s for s in suggestions if s.confidence >= self.min_confidence]

        # Log how many were filtered out
        if len(filtered) < len(suggestions):
            logger.debug(
                f"Filtered {len(suggestions) - len(filtered)} suggestions for test '{test_name}' below confidence threshold {self.min_confidence}"
            )

        # Deduplicate if enabled
        if self.deduplicate:
            deduplicated = self._deduplicate_suggestions(filtered)

            # Log how many duplicates were removed
            if len(deduplicated) < len(filtered):
                logger.debug(
                    f"Removed {len(filtered) - len(deduplicated)} duplicate suggestions for test '{test_name}'"
                )

            filtered = deduplicated

        # Sort by confidence (descending)
        filtered.sort(key=lambda s: s.confidence, reverse=True)

        # Limit number of suggestions per failure
        if (
            self.max_suggestions_per_failure > 0
            and len(filtered) > self.max_suggestions_per_failure
        ):
            logger.debug(
                f"Limiting suggestions for test '{test_name}' from {len(filtered)} to {self.max_suggestions_per_failure}"
            )
            filtered = filtered[: self.max_suggestions_per_failure]

        return filtered

    def _deduplicate_suggestions(self, suggestions: List[FixSuggestion]) -> List[FixSuggestion]:
        """
        Remove duplicate suggestions based on their content.

        Args:
            suggestions: List of suggestions to deduplicate

        Returns:
            Deduplicated list of suggestions
        """
        # Use a set to track unique fingerprints
        unique_fingerprints: Set[str] = set()
        unique_suggestions: List[FixSuggestion] = []

        for suggestion in suggestions:
            # Check if the suggestion has a fingerprint in code_changes
            fingerprint = None
            if suggestion.code_changes and isinstance(suggestion.code_changes, dict):
                fingerprint = suggestion.code_changes.get("fingerprint")

            # Generate a fingerprint if not present
            if not fingerprint:
                fingerprint = self._generate_suggestion_fingerprint(suggestion)

            # Add to results if the fingerprint is unique
            if fingerprint not in unique_fingerprints:
                unique_fingerprints.add(fingerprint)
                unique_suggestions.append(suggestion)

        return unique_suggestions

    def _deduplicate_dict_suggestions(
        self, suggestions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate dictionary suggestions based on their content.

        Args:
            suggestions: List of suggestion dictionaries to deduplicate

        Returns:
            Deduplicated list of suggestion dictionaries
        """
        # Use a set to track unique fingerprints
        unique_fingerprints: Set[str] = set()
        unique_suggestions: List[Dict[str, Any]] = []

        for suggestion in suggestions:
            # Check if the suggestion has a fingerprint in code_changes
            fingerprint = None
            code_changes = suggestion.get("code_changes", {})
            if isinstance(code_changes, dict):
                fingerprint = code_changes.get("fingerprint")

            # Generate a fingerprint if not present
            if not fingerprint:
                fingerprint = self._generate_dict_fingerprint(suggestion)

            # Add to results if the fingerprint is unique
            if fingerprint not in unique_fingerprints:
                unique_fingerprints.add(fingerprint)
                unique_suggestions.append(suggestion)

        return unique_suggestions

    def _generate_suggestion_fingerprint(self, suggestion: FixSuggestion) -> str:
        """
        Generate a fingerprint for a suggestion to identify duplicates.

        Args:
            suggestion: The suggestion to fingerprint

        Returns:
            A string fingerprint
        """
        # Combine key parts of the suggestion
        parts = [suggestion.suggestion or "", suggestion.explanation or ""]

        # Add code changes if present
        if suggestion.code_changes:
            if isinstance(suggestion.code_changes, dict):
                for key, value in suggestion.code_changes.items():
                    if key not in ("fingerprint", "source"):
                        parts.append(f"{key}:{value}")

        # Join and hash
        fingerprint = ":".join(parts)
        import hashlib

        return hashlib.md5(fingerprint.encode("utf-8")).hexdigest()

    def _generate_dict_fingerprint(self, suggestion: Dict[str, Any]) -> str:
        """
        Generate a fingerprint for a dictionary suggestion to identify duplicates.

        Args:
            suggestion: The suggestion dictionary to fingerprint

        Returns:
            A string fingerprint
        """
        # Combine key parts of the suggestion
        parts = [
            str(suggestion.get("suggestion", "")),
            str(suggestion.get("explanation", "")),
        ]

        # Add code changes if present
        code_changes = suggestion.get("code_changes", {})
        if isinstance(code_changes, dict):
            for key, value in code_changes.items():
                if key not in ("fingerprint", "source"):
                    parts.append(f"{key}:{value}")

        # Join and hash
        fingerprint = ":".join(parts)
        import hashlib

        return hashlib.md5(fingerprint.encode("utf-8")).hexdigest()
