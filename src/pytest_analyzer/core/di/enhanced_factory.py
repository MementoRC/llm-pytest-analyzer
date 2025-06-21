"""
Enhanced DI factory that integrates injector library with existing container.

This module provides a unified DI system that combines:
1. The existing custom Container for backward compatibility
2. The injector library for enhanced dependency injection
3. Interfaces for logging, metrics, and MCP components
"""

import logging
from typing import Optional, Type, TypeVar

from injector import Binder, Injector, Module, singleton

from .container import Container
from .implementations import (
    AnalysisSession,
    IAnalysisSession,
    ILogger,
    IMetrics,
    InMemoryMetrics,
    InMemorySessionManager,
    ISessionManager,
    StandardLogger,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)


class EnhancedDIModule(Module):
    """
    Injector module that configures enhanced DI services.
    """

    def configure(self, binder: Binder) -> None:
        """Configure enhanced services with the injector."""

        # Logging services
        binder.bind(ILogger, to=StandardLogger, scope=singleton)

        # Metrics services
        binder.bind(IMetrics, to=InMemoryMetrics, scope=singleton)

        # MCP session management
        binder.bind(ISessionManager, to=InMemorySessionManager, scope=singleton)

        # Analysis sessions (transient - new instance per request)
        binder.bind(IAnalysisSession, to=AnalysisSession)


class EnhancedDIContainer:
    """
    Unified DI container that combines legacy container with injector.

    This container provides:
    - Backward compatibility with existing DI usage
    - Enhanced functionality through injector library
    - Unified interface for service resolution
    """

    def __init__(self, legacy_container: Optional[Container] = None):
        """
        Initialize the enhanced DI container.

        Args:
            legacy_container: Optional existing container for backward compatibility
        """
        self._legacy_container = legacy_container or Container()
        self._injector = Injector([EnhancedDIModule()])

        logger.info("Enhanced DI container initialized with injector integration")

    def get_legacy_container(self) -> Container:
        """Get the legacy container for backward compatibility."""
        return self._legacy_container

    def get_injector(self) -> Injector:
        """Get the injector instance for enhanced DI."""
        return self._injector

    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve a service from either container.

        Resolution order:
        1. Try injector first for enhanced services
        2. Fall back to legacy container for existing services

        Args:
            service_type: The type of service to resolve

        Returns:
            An instance of the requested service

        Raises:
            Exception: If the service cannot be resolved from either container
        """
        # Try enhanced services first
        try:
            return self._injector.get(service_type)
        except Exception as injector_error:
            logger.debug(
                f"Service {service_type.__name__} not found in injector: {injector_error}"
            )

            # Fall back to legacy container
            try:
                return self._legacy_container.resolve(service_type)
            except Exception as legacy_error:
                logger.error(
                    f"Service {service_type.__name__} not found in either container. "
                    f"Injector: {injector_error}, Legacy: {legacy_error}"
                )
                raise

    def register_legacy(self, interface_type: Type[T], implementation, mode=None):
        """Register a service with the legacy container."""
        if mode:
            self._legacy_container.register(interface_type, implementation, mode)
        else:
            self._legacy_container.register_singleton(interface_type, implementation)

    def create_scope(self):
        """Create a scope using the legacy container."""
        return self._legacy_container.create_scope()


def create_enhanced_container(
    legacy_container: Optional[Container] = None,
) -> EnhancedDIContainer:
    """
    Create a new enhanced DI container.

    Args:
        legacy_container: Optional existing container to integrate

    Returns:
        A new EnhancedDIContainer instance
    """
    return EnhancedDIContainer(legacy_container)


def configure_enhanced_di(container: Container) -> EnhancedDIContainer:
    """
    Configure an existing container with enhanced DI capabilities.

    Args:
        container: Existing container to enhance

    Returns:
        Enhanced container with injector integration
    """
    enhanced = create_enhanced_container(container)

    # Register enhanced interfaces with the legacy container for fallback
    from .enhanced_service_collection import configure_enhanced_services

    configure_enhanced_services(container)

    logger.info("Enhanced DI configured with backward compatibility")
    return enhanced


# Global enhanced container instance
_global_enhanced_container: Optional[EnhancedDIContainer] = None


def get_global_enhanced_container() -> EnhancedDIContainer:
    """
    Get the global enhanced DI container.

    Returns:
        Global enhanced container instance
    """
    global _global_enhanced_container
    if _global_enhanced_container is None:
        from . import get_container

        legacy_container = get_container()
        _global_enhanced_container = configure_enhanced_di(legacy_container)

    return _global_enhanced_container


def set_global_enhanced_container(container: Optional[EnhancedDIContainer]) -> None:
    """
    Set the global enhanced container (primarily for testing).

    Args:
        container: Enhanced container to set as global, or None to reset
    """
    global _global_enhanced_container
    _global_enhanced_container = container


__all__ = [
    "EnhancedDIModule",
    "EnhancedDIContainer",
    "create_enhanced_container",
    "configure_enhanced_di",
    "get_global_enhanced_container",
    "set_global_enhanced_container",
]
