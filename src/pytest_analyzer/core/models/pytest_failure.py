from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class PytestFailure:
    """Represents a single test failure from pytest output."""
    test_name: str 
    test_file: str
    error_type: str
    error_message: str
    traceback: str
    line_number: int | None = None
    relevant_code: str | None = None
    raw_output_section: str | None = None
    related_project_files: List[str] = field(default_factory=list)
    # Added for grouping similar failures
    group_fingerprint: str | None = None
    suggestion: Dict[str, Any] | None = None

    # __post_init__ no longer needed as default factory ensures list


@dataclass
class FixSuggestion:
    """Represents a suggested fix for a test failure."""
    failure: PytestFailure
    suggestion: str
    confidence: float
    code_changes: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None