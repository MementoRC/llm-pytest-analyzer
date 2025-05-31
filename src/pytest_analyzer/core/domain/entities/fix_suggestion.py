import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..value_objects.suggestion_confidence import SuggestionConfidence


@dataclass
class FixSuggestion:
    """
    Domain entity representing a suggested fix for a test failure.

    This entity follows DDD principles:
    - Has an identity (id)
    - Contains business logic related to fix suggestions
    - Is mutable (suggestions can be refined or updated)
    """

    id: str
    failure_id: str
    suggestion_text: str
    code_changes: List[str] = field(default_factory=list)
    confidence: SuggestionConfidence = SuggestionConfidence.MEDIUM
    explanation: str = ""
    alternative_approaches: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        failure_id: str,
        suggestion_text: str,
        confidence: SuggestionConfidence = SuggestionConfidence.MEDIUM,
        explanation: str = "",
        code_changes: Optional[List[str]] = None,
        alternative_approaches: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "FixSuggestion":
        """
        Factory method to create a FixSuggestion with proper defaults.

        This method ensures proper initialization and follows DDD patterns
        for entity creation.
        """
        return cls(
            id=str(uuid.uuid4()),
            failure_id=failure_id,
            suggestion_text=suggestion_text,
            confidence=confidence,
            explanation=explanation,
            code_changes=code_changes or [],
            alternative_approaches=alternative_approaches or [],
            metadata=metadata or {},
        )

    @classmethod
    def create_from_score(
        cls,
        failure_id: str,
        suggestion_text: str,
        confidence_score: float,
        explanation: str = "",
        code_changes: Optional[List[str]] = None,
        alternative_approaches: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "FixSuggestion":
        """Create a FixSuggestion from a numeric confidence score."""
        confidence = SuggestionConfidence.from_score(confidence_score)

        return cls.create(
            failure_id=failure_id,
            suggestion_text=suggestion_text,
            confidence=confidence,
            explanation=explanation,
            code_changes=code_changes,
            alternative_approaches=alternative_approaches,
            metadata=metadata,
        )

    @property
    def is_high_confidence(self) -> bool:
        """Check if this suggestion has high confidence."""
        return self.confidence == SuggestionConfidence.HIGH

    @property
    def is_low_confidence(self) -> bool:
        """Check if this suggestion has low confidence."""
        return self.confidence == SuggestionConfidence.LOW

    @property
    def has_code_changes(self) -> bool:
        """Check if this suggestion includes code changes."""
        return bool(self.code_changes)

    @property
    def has_alternatives(self) -> bool:
        """Check if this suggestion includes alternative approaches."""
        return bool(self.alternative_approaches)

    @property
    def confidence_score(self) -> float:
        """Get the numeric confidence score."""
        return self.confidence.numeric_value

    def add_code_change(self, change: str) -> None:
        """Add a code change to this suggestion."""
        if change not in self.code_changes:
            self.code_changes.append(change)
            self._mark_updated()

    def add_alternative_approach(self, approach: str) -> None:
        """Add an alternative approach to this suggestion."""
        if approach not in self.alternative_approaches:
            self.alternative_approaches.append(approach)
            self._mark_updated()

    def update_confidence(self, confidence: SuggestionConfidence) -> None:
        """Update the confidence level of this suggestion."""
        self.confidence = confidence
        self._mark_updated()

    def update_confidence_from_score(self, score: float) -> None:
        """Update the confidence level from a numeric score."""
        self.confidence = SuggestionConfidence.from_score(score)
        self._mark_updated()

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to this suggestion."""
        self.metadata[key] = value
        self._mark_updated()

    def update_explanation(self, explanation: str) -> None:
        """Update the explanation for this suggestion."""
        self.explanation = explanation
        self._mark_updated()

    def _mark_updated(self) -> None:
        """Mark this suggestion as updated."""
        self.updated_at = datetime.now()

    def is_better_than(self, other: "FixSuggestion") -> bool:
        """
        Compare this suggestion with another to determine which is better.

        Considers confidence level and whether the suggestion has code changes.
        """
        if self.confidence > other.confidence:
            return True
        elif self.confidence == other.confidence:
            # Prefer suggestions with code changes
            return self.has_code_changes and not other.has_code_changes
        return False

    def merge_with(self, other: "FixSuggestion") -> None:
        """
        Merge another suggestion with this one.

        This combines the best aspects of both suggestions.
        """
        if other.confidence > self.confidence:
            self.confidence = other.confidence

        # Merge code changes
        for change in other.code_changes:
            if change not in self.code_changes:
                self.code_changes.append(change)

        # Merge alternative approaches
        for approach in other.alternative_approaches:
            if approach not in self.alternative_approaches:
                self.alternative_approaches.append(approach)

        # Merge metadata
        for key, value in other.metadata.items():
            if key not in self.metadata:
                self.metadata[key] = value

        self._mark_updated()

    def __eq__(self, other) -> bool:
        """Equality based on entity identity (id)."""
        if not isinstance(other, FixSuggestion):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on entity identity (id)."""
        return hash(self.id)
