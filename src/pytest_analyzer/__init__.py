"""pytest-analyzer - Enhanced pytest failure analyzer with intelligent fix suggestions.

This package provides tools for analyzing pytest test failures and suggesting fixes.
It features robust extraction strategies, resource monitoring, and intelligent
fix suggestions based on error patterns.

Example:
    >>> from pytest_analyzer import PytestAnalyzerService, Settings
    >>> settings = Settings(max_failures=5)
    >>> analyzer = PytestAnalyzerService(settings=settings)
    >>> suggestions = analyzer.run_and_analyze("tests/")
    >>> for suggestion in suggestions:
    ...     print(suggestion.suggestion)

Attributes:
    __version__ (str): The version of the pytest-analyzer package.
    PytestAnalyzerService (type): Main service for analyzing pytest failures.
    PytestFailure (type): Data model for pytest failures.
    FixSuggestion (type): Data model for fix suggestions.
    Settings (type): Configuration settings.
    load_settings (Callable): Function to load settings.
    PathResolver (type): Utility for path resolution.
"""

from .__version__ import __version__
from .core.analyzer_service import PytestAnalyzerService
from .core.models.pytest_failure import FixSuggestion, PytestFailure
from .utils.path_resolver import PathResolver
from .utils.settings import Settings, load_settings

__all__ = [
    "PytestAnalyzerService",
    "PytestFailure",
    "FixSuggestion",
    "Settings",
    "load_settings",
    "PathResolver",
    "__version__",
]
