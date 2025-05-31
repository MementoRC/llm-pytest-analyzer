from enum import Enum
from typing import Union


class SuggestionConfidence(Enum):
    """Enumeration of confidence levels for fix suggestions."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @classmethod
    def from_score(cls, score: Union[float, int]) -> "SuggestionConfidence":
        """Convert numeric confidence score to confidence level."""
        if score >= 0.8:
            return cls.HIGH
        elif score >= 0.5:
            return cls.MEDIUM
        else:
            return cls.LOW

    @property
    def numeric_value(self) -> float:
        """Get the numeric representation of confidence level."""
        return {
            SuggestionConfidence.HIGH: 0.9,
            SuggestionConfidence.MEDIUM: 0.7,
            SuggestionConfidence.LOW: 0.3,
        }[self]

    def __lt__(self, other: "SuggestionConfidence") -> bool:
        """Allow comparison of confidence levels."""
        order = {
            SuggestionConfidence.LOW: 1,
            SuggestionConfidence.MEDIUM: 2,
            SuggestionConfidence.HIGH: 3,
        }
        return order[self] < order[other]

    def __le__(self, other: "SuggestionConfidence") -> bool:
        """Allow comparison of confidence levels."""
        return self < other or self == other

    def __gt__(self, other: "SuggestionConfidence") -> bool:
        """Allow comparison of confidence levels."""
        return not self <= other

    def __ge__(self, other: "SuggestionConfidence") -> bool:
        """Allow comparison of confidence levels."""
        return not self < other
