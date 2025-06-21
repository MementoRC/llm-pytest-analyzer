import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PytestFailure:
    """Represents a single test failure from pytest output."""

    test_name: str
    test_file: str
    error_type: str
    error_message: str
    traceback: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()), init=False)
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
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    failure_id: Optional[str] = None
