"""Schema definitions for the suggest_fixes MCP tool.

This tool generates fix suggestions from raw pytest output.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import (
    FixSuggestionData,
    MCPRequest,
    MCPResponse,
    PytestFailureData,
)


@dataclass
class SuggestFixesRequest(MCPRequest):
    """Request schema for suggest_fixes MCP tool.

    Generates fix suggestions from raw pytest output string.

    Example:
        request = SuggestFixesRequest(
            tool_name="suggest_fixes",
            raw_output="=== FAILURES ===\ntest_example.py::test_func - AssertionError...",
            context={"project_root": "/path/to/project"},
            max_suggestions=5
        )
    """

    raw_output: str
    context: Dict[str, Any] = field(default_factory=dict)
    max_suggestions: int = 10
    confidence_threshold: float = 0.3
    include_alternatives: bool = True
    filter_by_type: Optional[List[str]] = None

    def validate(self) -> List[str]:
        """Validate request data."""
        errors = super().validate()

        # Validate raw_output
        if not self.raw_output or not self.raw_output.strip():
            errors.append("raw_output is required and cannot be empty")

        # Validate max_suggestions
        if self.max_suggestions <= 0:
            errors.append("max_suggestions must be positive")
        elif self.max_suggestions > 100:
            errors.append("max_suggestions cannot exceed 100")

        # Validate confidence_threshold
        if not (0.0 <= self.confidence_threshold <= 1.0):
            errors.append("confidence_threshold must be between 0.0 and 1.0")

        return errors


@dataclass
class SuggestFixesResponse(MCPResponse):
    """Response schema for suggest_fixes MCP tool.

    Contains fix suggestions generated from raw pytest output.
    """

    suggestions: List[FixSuggestionData] = field(default_factory=list)
    failures: List[PytestFailureData] = field(default_factory=list)
    confidence_score: float = 0.0
    parsing_warnings: List[str] = field(default_factory=list)
    analysis_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Calculate confidence score after initialization."""
        if self.suggestions and self.confidence_score == 0.0:
            total_confidence = sum(s.confidence_score for s in self.suggestions)
            self.confidence_score = total_confidence / len(self.suggestions)

    def get_high_confidence_suggestions(
        self, threshold: float = 0.8
    ) -> List[FixSuggestionData]:
        """Get suggestions with confidence above threshold."""
        return [s for s in self.suggestions if s.confidence_score >= threshold]


__all__ = ["SuggestFixesRequest", "SuggestFixesResponse"]
