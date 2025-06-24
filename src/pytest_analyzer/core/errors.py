"""
Centralized error handling module for pytest_analyzer.

This module defines a hierarchy of exceptions for the pytest_analyzer package
to provide more granular error handling and better error messages. It includes
a BaseError for capturing context, error codes, and original exceptions.
"""

from typing import Any, Dict, Optional


class BaseError(Exception):
    """Base class for all custom exceptions in the application."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        """
        Initialize the BaseError.

        Args:
            message: The primary error message.
            error_code: A unique code for this error type (e.g., 'CONFIG_001').
            context: A dictionary of contextual information related to the error.
            original_exception: The original exception that was caught and wrapped.
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.original_exception = original_exception

    def __str__(self) -> str:
        """Create a string representation of the error."""
        parts = []
        if self.error_code:
            parts.append(f"[{self.error_code}]")
        parts.append(self.message)

        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"Context: ({context_str})")

        if self.original_exception:
            parts.append(
                f"--> Caused by: {type(self.original_exception).__name__}: {self.original_exception}"
            )

        return " ".join(parts)


class PytestAnalyzerError(BaseError):
    """Base exception class for all pytest_analyzer errors."""

    def __init__(
        self,
        message: Optional[str] = None,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message or "An error occurred during pytest analysis",
            error_code=error_code,
            context=context,
            original_exception=original_exception,
        )


class ConfigurationError(PytestAnalyzerError):
    """Error related to configuration issues."""

    def __init__(
        self,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message or "Invalid configuration specified",
            error_code="CONFIG_001",
            context=context,
            original_exception=original_exception,
        )


class ExtractionError(PytestAnalyzerError):
    """Error during test failure extraction."""

    def __init__(
        self,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message or "Failed to extract test failures",
            error_code="EXTRACT_001",
            context=context,
            original_exception=original_exception,
        )


class AnalysisError(PytestAnalyzerError):
    """Error during test failure analysis."""

    def __init__(
        self,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message or "Failed to analyze test failures",
            error_code="ANALYSIS_001",
            context=context,
            original_exception=original_exception,
        )


class ParsingError(PytestAnalyzerError):
    """Error during response parsing."""

    def __init__(
        self,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message or "Failed to parse response",
            error_code="PARSE_001",
            context=context,
            original_exception=original_exception,
        )


class LLMServiceError(PytestAnalyzerError):
    """Error in LLM service communication."""

    def __init__(
        self,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message or "Error communicating with language model service",
            error_code="LLM_001",
            context=context,
            original_exception=original_exception,
        )


class FixApplicationError(PytestAnalyzerError):
    """Error applying fixes to code."""

    def __init__(
        self,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message or "Failed to apply suggested fix",
            error_code="FIX_APPLY_001",
            context=context,
            original_exception=original_exception,
        )


class DependencyResolutionError(PytestAnalyzerError):
    """Error resolving dependencies from the container."""

    def __init__(
        self,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message or "Failed to resolve dependency",
            error_code="DEPS_001",
            context=context,
            original_exception=original_exception,
        )


class RetryError(PytestAnalyzerError):
    """Error indicating an operation failed after all retry attempts."""

    def __init__(
        self,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message or "Operation failed after all retry attempts",
            error_code="RETRY_001",
            context=context,
            original_exception=original_exception,
        )


class CircuitBreakerOpenError(PytestAnalyzerError):
    """Error indicating that the circuit breaker is open and preventing calls."""

    def __init__(
        self,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        super().__init__(
            message or "Circuit breaker is open",
            error_code="CIRCUIT_001",
            context=context,
            original_exception=original_exception,
        )
