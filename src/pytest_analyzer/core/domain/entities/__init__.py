"""
Domain entities for the pytest analyzer.

Entities are objects that have an identity and lifecycle. They represent
core business concepts and contain the business logic related to those concepts.
"""

from .fix_suggestion import FixSuggestion
from .pytest_failure import PytestFailure

__all__ = [
    "FixSuggestion",
    "PytestFailure",
]
