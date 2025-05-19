"""
pytest-analyzer - Enhanced pytest failure analyzer with intelligent fix suggestions.

This package provides tools for analyzing pytest test failures and suggesting fixes.
It features robust extraction strategies, resource monitoring, and intelligent
fix suggestions based on error patterns.
"""

from .__version__ import __version__

# Import from the facade and backward compatibility module
from .core import PytestAnalyzerFacade, PytestAnalyzerService
from .core.models.pytest_failure import FixSuggestion, PytestFailure
from .utils.path_resolver import PathResolver
from .utils.settings import Settings, load_settings

# Define the public API
__all__ = [
    "PytestAnalyzerService",  # Backward compatibility
    "PytestAnalyzerFacade",  # New facade
    "PytestFailure",  # Data models
    "FixSuggestion",
    "Settings",  # Configuration
    "load_settings",
    "PathResolver",  # Utilities
    "__version__",
]
