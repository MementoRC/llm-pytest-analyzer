"""Infrastructure layer for external concerns and implementations.

This layer contains implementations of interfaces defined in the domain layer
and handles external concerns like databases, web services, file systems.
"""

from .base_factory import BaseFactory

__all__ = ["BaseFactory"]
