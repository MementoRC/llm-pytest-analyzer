from dataclasses import dataclass
from typing import Optional, List, Dict, Any


@dataclass
class PytestFailure:
    """Represents a single test failure from pytest output."""
    test_name: str 
    test_file: str
    error_type: str
    error_message: str
    traceback: str
    line_number: Optional[int] = None
    relevant_code: Optional[str] = None
    raw_output_section: Optional[str] = None
    related_project_files: List[str] = None
    # Added for grouping similar failures
    group_fingerprint: Optional[str] = None
    suggestion: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.related_project_files is None:
            self.related_project_files = []


@dataclass
class FixSuggestion:
    """Represents a suggested fix for a test failure."""
    failure: PytestFailure
    suggestion: str
    confidence: float
    code_changes: Optional[Dict[str, Any]] = None
    explanation: Optional[str] = None