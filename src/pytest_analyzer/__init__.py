"""
pytest-analyzer - Enhanced pytest failure analyzer with intelligent fix suggestions.

This package provides tools for analyzing pytest test failures and suggesting fixes.
It features robust extraction strategies, resource monitoring, and intelligent
fix suggestions based on error patterns.
"""

from .__version__ import __version__
from .core.analyzer_service import PytestAnalyzerService
from .core.models.pytest_failure import PytestFailure, FixSuggestion
from .utils.settings import Settings, load_settings
from .utils.path_resolver import PathResolver

# Define the public API
__all__ = [
    'PytestAnalyzerService',  # Main service
    'PytestFailure',          # Data models
    'FixSuggestion',
    'Settings',               # Configuration
    'load_settings',
    'PathResolver',           # Utilities
    '__version__'
]
