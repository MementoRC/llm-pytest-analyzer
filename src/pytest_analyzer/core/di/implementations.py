"""
Default implementations for enhanced DI interfaces.
"""

import logging
from typing import Any, Dict, Protocol

# --- Interfaces ---


class ILogger(Protocol):
    """Interface for logging services."""

    def log(self, message: str) -> None:
        """Log a message."""
        ...


class IMetrics(Protocol):
    """Interface for metrics recording services."""

    def record(self, name: str, value: float) -> None:
        """Record a metric value."""
        ...


class ISessionManager(Protocol):
    """Interface for session management services."""

    def start(self) -> None:
        """Start a session."""
        ...

    def end(self) -> None:
        """End a session."""
        ...


class IAnalysisSession(Protocol):
    """Interface for an analysis session."""

    def analyze(self, data: Any) -> str:
        """Analyze the given data."""
        ...


# --- Implementations ---


class StandardLogger:
    """Standard logger that uses Python's logging module."""

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__module__)

    def log(self, message: str) -> None:
        """Log a message using the standard logger."""
        self._logger.info(message)


class InMemoryMetrics:
    """In-memory implementation of metrics recording."""

    def __init__(self):
        """Initialize with an empty metrics dictionary."""
        self.metrics: Dict[str, float] = {}

    def record(self, name: str, value: float) -> None:
        """Record a metric value in the in-memory dictionary."""
        self.metrics[name] = value


class InMemorySessionManager:
    """In-memory implementation of session management."""

    def __init__(self):
        """Initialize session state."""
        self.started = False
        self.ended = False

    def start(self) -> None:
        """Mark the session as started."""
        self.started = True

    def end(self) -> None:
        """Mark the session as ended."""
        self.ended = True


class AnalysisSession:
    """
    Represents a transient analysis session.

    This implementation is simple and can be extended with dependencies
    that will be injected by the DI container.
    """

    def analyze(self, data: Any) -> str:
        """Perform analysis on the provided data."""
        return f"analyzed data: {data}"


__all__ = [
    "ILogger",
    "IMetrics",
    "ISessionManager",
    "IAnalysisSession",
    "StandardLogger",
    "InMemoryMetrics",
    "InMemorySessionManager",
    "AnalysisSession",
]
