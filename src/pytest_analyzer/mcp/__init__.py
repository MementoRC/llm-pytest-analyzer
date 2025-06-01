"""MCP integration module for pytest-analyzer.

Provides Model Context Protocol server implementation and tools for
test analysis and fix suggestions.
"""

from .server import PytestAnalyzerMCPServer

__all__ = [
    "PytestAnalyzerMCPServer",
]
