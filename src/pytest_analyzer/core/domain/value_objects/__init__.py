"""
Value objects for the domain layer.

Value objects are immutable objects that are defined by their attributes
rather than their identity. They represent concepts from the domain that
are characterized by their values.
"""

from .failure_type import FailureType
from .suggestion_confidence import SuggestionConfidence
from .test_location import TestLocation

__all__ = [
    "FailureType",
    "SuggestionConfidence",
    "TestLocation",
]
