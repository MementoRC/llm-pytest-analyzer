"""
Natural Language Processing module for pytest-analyzer.

This module provides natural language query processing capabilities,
allowing users to interact with pytest-analyzer using plain English.
"""

from .intent_recognizer import IntentRecognizer, QueryIntent
from .query_processor import NLQueryProcessor
from .response_generator import NLResponseGenerator, ResponseGenerator

__all__ = [
    "NLQueryProcessor",
    "IntentRecognizer",
    "QueryIntent",
    "ResponseGenerator",
    "NLResponseGenerator",
]
