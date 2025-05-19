"""
Core functionality for pytest-analyzer.

This package contains the core components of the pytest-analyzer library.
"""

# Expose the facade and the backward-compatible service
from .analyzer_facade import PytestAnalyzerFacade  # noqa: F401
from .backward_compat import PytestAnalyzerService  # noqa: F401

# Define public exports
__all__ = ["PytestAnalyzerFacade", "PytestAnalyzerService"]
