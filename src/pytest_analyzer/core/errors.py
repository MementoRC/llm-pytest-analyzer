"""
Centralized error handling module for pytest_analyzer.

This module defines a hierarchy of exceptions for the pytest_analyzer package
to provide more granular error handling and better error messages.
"""


class PytestAnalyzerError(Exception):
    """Base exception class for all pytest_analyzer errors."""

    def __init__(self, message: str = None, *args):
        self.message = message or "An error occurred during pytest analysis"
        super().__init__(self.message, *args)


class ConfigurationError(PytestAnalyzerError):
    """Error related to configuration issues."""

    def __init__(self, message: str = None, *args):
        self.message = message or "Invalid configuration specified"
        super().__init__(self.message, *args)


class ExtractionError(PytestAnalyzerError):
    """Error during test failure extraction."""

    def __init__(self, message: str = None, *args):
        self.message = message or "Failed to extract test failures"
        super().__init__(self.message, *args)


class AnalysisError(PytestAnalyzerError):
    """Error during test failure analysis."""

    def __init__(self, message: str = None, *args):
        self.message = message or "Failed to analyze test failures"
        super().__init__(self.message, *args)


class ParsingError(PytestAnalyzerError):
    """Error during response parsing."""

    def __init__(self, message: str = None, *args):
        self.message = message or "Failed to parse response"
        super().__init__(self.message, *args)


class LLMServiceError(PytestAnalyzerError):
    """Error in LLM service communication."""

    def __init__(self, message: str = None, *args):
        self.message = message or "Error communicating with language model service"
        super().__init__(self.message, *args)


class FixApplicationError(PytestAnalyzerError):
    """Error applying fixes to code."""

    def __init__(self, message: str = None, *args):
        self.message = message or "Failed to apply suggested fix"
        super().__init__(self.message, *args)
