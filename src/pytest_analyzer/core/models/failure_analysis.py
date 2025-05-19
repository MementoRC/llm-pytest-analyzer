"""
FailureAnalysis model for pytest_analyzer.

This module defines data structures for representing failure analysis results.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .pytest_failure import PytestFailure


@dataclass
class FailureAnalysis:
    """
    Represents an analysis of a test failure.

    This class stores the analysis results from examining a pytest failure,
    including root cause, error categorization, and suggested fixes.
    """

    failure: PytestFailure
    root_cause: str
    error_type: str
    suggested_fixes: List[str] = field(default_factory=list)
    confidence: float = 0.7
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

        # Ensure valid confidence value
        self.confidence = max(0.0, min(1.0, self.confidence))
