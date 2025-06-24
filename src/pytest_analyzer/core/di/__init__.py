"""
Dependency Injection module for pytest-analyzer.

This module provides a dependency injection container and related utilities
for managing component dependencies and facilitating testing.
"""

from typing import Optional

from .container import Container, Registration, RegistrationMode
from .decorators import factory, inject, register, singleton, transient
from .service_collection import (
    configure_services,
    get_service,
    initialize_container,
)

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


# Enhanced DI functionality
_ENHANCED_DI_AVAILABLE = False

try:
    import importlib.util

    if importlib.util.find_spec("injector") is not None:
        from .enhanced_service_collection import (
            configure_enhanced_services,
            get_enhanced_container,
        )

        _ENHANCED_DI_AVAILABLE = True
        # Add to globals for dynamic exports
        globals()["configure_enhanced_services"] = configure_enhanced_services
        globals()["get_enhanced_container"] = get_enhanced_container
except ImportError:
    pass


def is_enhanced_di_available() -> bool:
    """Check if enhanced DI with injector library is available."""
    return _ENHANCED_DI_AVAILABLE


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
    # Service collection
    "configure_services",
    "get_service",
    "initialize_container",
    # Enhanced DI (if available)
    "is_enhanced_di_available",
]

# Add enhanced DI to exports if available
if _ENHANCED_DI_AVAILABLE:
    __all__.extend(
        [
            "configure_enhanced_services",
            "get_enhanced_container",
        ]
    )
