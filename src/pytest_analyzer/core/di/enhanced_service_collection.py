"""
Service collection for enhanced DI.

This module provides functions to configure and access the enhanced DI container,
bridging the legacy container with the new injector-based system.
"""

from typing import TYPE_CHECKING

from .implementations import IAnalysisSession, ILogger, IMetrics, ISessionManager

if TYPE_CHECKING:
    from .container import Container
    from .enhanced_factory import EnhancedDIContainer


def configure_enhanced_services(container: "Container") -> None:
    """
    Register enhanced services with the legacy container for fallback compatibility.

    This function registers factories in the legacy container that delegate
    resolution to the enhanced container. This allows code that still uses
    the legacy `container.resolve()` to get instances of services managed
    by the new injector-based system.

    Args:
        container: The legacy container instance.
    """
    from .enhanced_factory import get_global_enhanced_container

    enhanced_container = get_global_enhanced_container()

    # Register factories that delegate to the enhanced container
    container.register_factory(ILogger, lambda: enhanced_container.resolve(ILogger))
    container.register_factory(IMetrics, lambda: enhanced_container.resolve(IMetrics))
    container.register_factory(
        ISessionManager, lambda: enhanced_container.resolve(ISessionManager)
    )
    container.register_factory(
        IAnalysisSession, lambda: enhanced_container.resolve(IAnalysisSession)
    )


def get_enhanced_container() -> "EnhancedDIContainer":
    """
    Get the global enhanced DI container instance.

    This is the primary entry point for accessing the unified DI system.

    Returns:
        The global EnhancedDIContainer instance.
    """
    from .enhanced_factory import get_global_enhanced_container

    return get_global_enhanced_container()


__all__ = ["configure_enhanced_services", "get_enhanced_container"]
