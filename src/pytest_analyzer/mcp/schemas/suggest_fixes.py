"""Schema definitions for the suggest_fixes MCP tool.

This tool generates fix suggestions from raw pytest output.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from . import (
    FixSuggestionData,
    PytestFailureData,
)


@dataclass
class SuggestFixesRequest:
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

    # Required fields first
    tool_name: str
    raw_output: str

    # Optional fields with defaults
    request_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    max_suggestions: int = 10
    confidence_threshold: float = 0.3
    include_alternatives: bool = True
    filter_by_type: Optional[List[str]] = None

    def validate(self) -> List[str]:
        """Validate request data."""
        errors = []

        # Validate common fields
        if not self.tool_name:
            errors.append("tool_name is required")
        if not self.request_id:
            errors.append("request_id is required")

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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict

        return asdict(self)


@dataclass
class SuggestFixesResponse:
    """Response schema for suggest_fixes MCP tool.

    Contains fix suggestions generated from raw pytest output.
    """

    # Required fields first
    success: bool
    request_id: str

    # Optional fields with defaults
    execution_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from dataclasses import asdict

        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        import json

        return json.dumps(self.to_dict(), indent=2)


__all__ = ["SuggestFixesRequest", "SuggestFixesResponse"]
