"""
pytest_analyzer package for analyzing pytest failures and suggesting fixes.

This package provides robust extraction strategies that avoid the regex-based infinite loop
issues of the original test_analyzer implementation, with a focus on:

- Structured data extraction (JSON, XML) instead of raw text parsing
- Resource management with timeouts and memory limits
- Direct pytest plugin integration
- Modular design with separate extraction and analysis components
"""

from .core.analyzer_service import TestAnalyzerService
from .core.models.test_failure import TestFailure, FixSuggestion
from .utils.settings import Settings, load_settings

__version__ = "0.1.0"
__all__ = ["TestAnalyzerService", "TestFailure", "FixSuggestion", "Settings", "load_settings"]