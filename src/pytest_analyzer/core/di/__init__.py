"""
Dependency Injection module for pytest-analyzer.

This module provides a dependency injection container and related utilities
for managing component dependencies and facilitating testing.
"""

from typing import Optional

from .container import Container, Registration, RegistrationMode
from .decorators import factory, inject, register, singleton, transient

# Global container instance (lazy initialization)
_global_container = None


def get_container() -> Container:
    """
    Get the global container instance.

    If no global container exists, one will be created.

    Returns:
        The global Container instance
    """
    global _global_container
    if _global_container is None:
        _global_container = Container()
    return _global_container


def set_container(container: Optional[Container]) -> None:
    """
    Set the global container instance.

    This function is primarily for testing purposes, allowing
    the container to be replaced with a pre-configured one.
    Passing None will reset the global container.

    Args:
        container: The Container instance to use globally, or None to reset
    """
    global _global_container
    _global_container = container


__all__ = [
    "Container",
    "RegistrationMode",
    "Registration",
    "register",
    "singleton",
    "transient",
    "factory",
    "inject",
    "get_container",
    "set_container",
]
