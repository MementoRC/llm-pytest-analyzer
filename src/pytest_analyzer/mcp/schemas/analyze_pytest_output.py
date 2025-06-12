"""Schema definitions for the analyze_pytest_output MCP tool.

This tool analyzes pytest output files (JSON, XML, text) and returns fix suggestions.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from . import (
    FixSuggestionData,
    PytestFailureData,
    validate_file_path,
    validate_output_format,
)


@dataclass
class AnalyzePytestOutputRequest:
    """Request schema for analyze_pytest_output MCP tool.

    Analyzes pytest output files and generates fix suggestions.

    Example:
        request = AnalyzePytestOutputRequest(
            tool_name="analyze_pytest_output",
            file_path="/path/to/pytest_output.json",
            format="json",
            options={"max_suggestions": 5, "include_traceback": True}
        )
    """

    tool_name: str
    file_path: str
    format: str = "json"  # json, xml, text, junit
    max_suggestions: int = 10
    include_traceback: bool = True
    request_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: Dict[str, Any] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
    filter_by_type: Optional[List[str]] = None  # Filter by failure types

    def validate(self) -> List[str]:
        """Validate request data."""
        errors = []

        # Validate common fields
        if not self.tool_name:
            errors.append("tool_name is required")
        if not self.request_id:
            errors.append("request_id is required")

        # Validate file path
        errors.extend(validate_file_path(self.file_path))

        # Validate format
        errors.extend(validate_output_format(self.format))

        # Validate max_suggestions
        if self.max_suggestions <= 0:
            errors.append("max_suggestions must be positive")
        elif self.max_suggestions > 100:
            errors.append("max_suggestions cannot exceed 100")

        # Validate filter_by_type if provided
        if self.filter_by_type is not None:
            valid_types = {
                "assertion_error",
                "exception",
                "import_error",
                "syntax_error",
                "timeout",
            }
            for failure_type in self.filter_by_type:
                if failure_type not in valid_types:
                    errors.append(
                        f"Invalid failure type '{failure_type}'. Must be one of: {valid_types}"
                    )

        return errors


@dataclass
class AnalyzePytestOutputResponse:
    """Response schema for analyze_pytest_output MCP tool.

    Contains fix suggestions generated from pytest output analysis.

    Example:
        response = AnalyzePytestOutputResponse(
            success=True,
            request_id="123e4567-e89b-12d3-a456-426614174000",
            suggestions=[
                FixSuggestionData(
                    id="suggestion-1",
                    failure_id="failure-1",
                    suggestion_text="Fix assertion error by updating expected value",
                    confidence_score=0.85
                )
            ],
            failures=[
                PytestFailureData(
                    id="failure-1",
                    test_name="test_example",
                    file_path="tests/test_example.py",
                    failure_message="AssertionError: expected 5, got 3",
                    failure_type="assertion_error"
                )
            ],
            execution_time_ms=1250
        )
    """

    success: bool
    request_id: str
    execution_time_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[FixSuggestionData] = field(default_factory=list)
    failures: List[PytestFailureData] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    parsing_errors: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize summary data after creation."""
        if not self.summary:
            self.summary = {
                "total_failures": len(self.failures),
                "total_suggestions": len(self.suggestions),
                "failure_types": self._count_failure_types(),
                "average_confidence": self._calculate_average_confidence(),
            }

    def _count_failure_types(self) -> Dict[str, int]:
        """Count failures by type."""
        counts = {}
        for failure in self.failures:
            failure_type = failure.failure_type
            counts[failure_type] = counts.get(failure_type, 0) + 1
        return counts

    def _calculate_average_confidence(self) -> float:
        """Calculate average confidence score of suggestions."""
        if not self.suggestions:
            return 0.0

        total_confidence = sum(
            suggestion.confidence_score for suggestion in self.suggestions
        )
        return total_confidence / len(self.suggestions)

    def get_high_confidence_suggestions(
        self, threshold: float = 0.8
    ) -> List[FixSuggestionData]:
        """Get suggestions with confidence above threshold."""
        return [s for s in self.suggestions if s.confidence_score >= threshold]

    def get_failures_by_type(self, failure_type: str) -> List[PytestFailureData]:
        """Get failures of a specific type."""
        return [f for f in self.failures if f.failure_type == failure_type]


__all__ = ["AnalyzePytestOutputRequest", "AnalyzePytestOutputResponse"]
