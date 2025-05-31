"""Exception definitions for the application.

This module defines all custom exceptions and error types
used throughout the application layers.
"""

from typing import Optional


class BaseError(Exception):
    """Base class for custom exceptions in the application."""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception

    def __str__(self) -> str:
        if self.original_exception:
            return f"{self.message}: {self.original_exception}"
        return self.message
