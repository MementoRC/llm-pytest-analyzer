"""
Service collection for dependency registration.

This module provides functionality to register all services and dependencies
for the pytest analyzer with the DI container.
"""

import logging
from typing import Optional, Type, TypeVar

from ...utils.path_resolver import PathResolver
from ...utils.settings import Settings
from ..analysis.failure_analyzer import FailureAnalyzer
from ..analysis.fix_applier import FixApplier
from ..analysis.fix_suggester import FixSuggester
from ..analysis.llm_suggester import LLMSuggester

# Import at function scope to avoid circular imports
from ..analyzer_state_machine import AnalyzerContext, AnalyzerStateMachine
from ..llm.backward_compat import LLMService
from ..llm.llm_service_protocol import LLMServiceProtocol
from .container import Container

logger = logging.getLogger(__name__)

T = TypeVar("T")


def configure_services(
    container: Container, settings: Optional[Settings] = None
) -> Container:
    """
    Configure all services and dependencies needed for the pytest analyzer.

    This function registers all services with the dependency injection container,
    creating a fully configured environment for analyzing pytest failures.

    Args:
        container: The DI container to configure
        settings: Optional Settings object (creates default settings if None)

    Returns:
        The configured container for chaining
    """
    # Register or use settings
    if settings:
        container.register_instance(Settings, settings)
    else:
        # Register a new Settings instance if none provided
        container.register_factory(Settings, lambda: Settings())

    # Register utility services
    container.register_factory(
        PathResolver, lambda: PathResolver(container.resolve(Settings).project_root)
    )

    # Register analyzer context (dependency for AnalyzerStateMachine)
    container.register_factory(
        AnalyzerContext, lambda: _create_analyzer_context(container)
    )

    # Register LLM service
    container.register_factory(
        LLMServiceProtocol, lambda: _create_llm_service(container)
    )

    # Register analysis components
    container.register_singleton(FailureAnalyzer, FailureAnalyzer)
    container.register_singleton(FixSuggester, FixSuggester)
    container.register_singleton(FixApplier, FixApplier)
    container.register_factory(LLMSuggester, lambda: _create_llm_suggester(container))

    # Register state machine
    container.register_singleton(AnalyzerStateMachine, AnalyzerStateMachine)

    # Register analyzers - import here to avoid circular imports
    from ..analyzer_service_di import DIPytestAnalyzerService

    # Register the analyzer service with a factory that explicitly passes the LLM service
    container.register_factory(
        DIPytestAnalyzerService,
        lambda:
        # Create analyzer service
        DIPytestAnalyzerService(
            settings=container.resolve(Settings),
            path_resolver=container.resolve(PathResolver),
            state_machine=container.resolve(AnalyzerStateMachine),
            # Only get LLM service if use_llm is True, otherwise pass None
            llm_service=(
                container.resolve(LLMServiceProtocol)
                if container.resolve(Settings).use_llm
                else None
            ),
        ),
    )

    return container


def _create_analyzer_context(container: Container = None) -> AnalyzerContext:
    """
    Factory function to create an analyzer context with all required dependencies.

    Args:
        container: Optional container, if not provided the global container will be used

    Returns:
        A configured AnalyzerContext instance
    """
    # If no container provided, get the global container
    if container is None:
        from . import get_container

        container = get_container()

    # Get a direct reference to the Settings resolve method to avoid circular references
    settings_resolver = (
        container._registrations[Settings].instance
        or container._registrations[Settings].factory
    )
    settings = settings_resolver() if callable(settings_resolver) else settings_resolver

    # Get dependencies directly to avoid circular reference issues
    path_resolver_resolver = (
        container._registrations[PathResolver].instance
        or container._registrations[PathResolver].factory
    )
    path_resolver = (
        path_resolver_resolver()
        if callable(path_resolver_resolver)
        else path_resolver_resolver
    )

    # Create LLM service if enabled
    llm_service = None
    if settings.use_llm and LLMServiceProtocol in container._registrations:
        llm_resolver = (
            container._registrations[LLMServiceProtocol].instance
            or container._registrations[LLMServiceProtocol].factory
        )
        llm_service = llm_resolver() if callable(llm_resolver) else llm_resolver

    # Create context
    context = AnalyzerContext(
        settings=settings, path_resolver=path_resolver, llm_service=llm_service
    )

    # Add analysis components if they're registered
    if FailureAnalyzer in container._registrations:
        resolver = (
            container._registrations[FailureAnalyzer].instance
            or container._registrations[FailureAnalyzer].factory
        )
        context.analyzer = resolver() if callable(resolver) else resolver

    if FixSuggester in container._registrations:
        resolver = (
            container._registrations[FixSuggester].instance
            or container._registrations[FixSuggester].factory
        )
        context.suggester = resolver() if callable(resolver) else resolver

    if FixApplier in container._registrations:
        resolver = (
            container._registrations[FixApplier].instance
            or container._registrations[FixApplier].factory
        )
        context.fix_applier = resolver() if callable(resolver) else resolver

    # Add LLM suggester if enabled
    if settings.use_llm and LLMSuggester in container._registrations:
        resolver = (
            container._registrations[LLMSuggester].instance
            or container._registrations[LLMSuggester].factory
        )
        context.llm_suggester = resolver() if callable(resolver) else resolver

    return context


def _create_llm_service(container: Container = None) -> Optional[LLMServiceProtocol]:
    """
    Factory function to create an LLM service if enabled in settings.

    Args:
        container: Optional container, if not provided the global container will be used

    Returns:
        An LLM service instance if use_llm is True, None otherwise
    """
    # If no container provided, get the global container
    if container is None:
        from . import get_container

        container = get_container()

    # Get settings directly to avoid circular references
    if Settings in container._registrations:
        settings_resolver = (
            container._registrations[Settings].instance
            or container._registrations[Settings].factory
        )
        settings = (
            settings_resolver() if callable(settings_resolver) else settings_resolver
        )
    else:
        # Fall back to default settings
        settings = Settings()

    # Always check use_llm - make sure we don't create a service unless it's enabled
    if not settings.use_llm:
        return None

    # Create LLM service if we reach here (meaning use_llm is True)
    return LLMService(timeout_seconds=settings.llm_timeout)


def _create_llm_suggester(container: Container = None) -> Optional[LLMSuggester]:
    """
    Factory function to create an LLM suggester if enabled in settings.

    Args:
        container: Optional container, if not provided the global container will be used

    Returns:
        An LLMSuggester instance if use_llm is True, None otherwise
    """
    # If no container provided, get the global container
    if container is None:
        from . import get_container

        container = get_container()

    # Get settings directly to avoid circular references
    if Settings in container._registrations:
        settings_resolver = (
            container._registrations[Settings].instance
            or container._registrations[Settings].factory
        )
        settings = (
            settings_resolver() if callable(settings_resolver) else settings_resolver
        )
    else:
        # Fall back to default settings
        settings = Settings()

    # Create LLM suggester if enabled
    if settings.use_llm and LLMServiceProtocol in container._registrations:
        llm_resolver = (
            container._registrations[LLMServiceProtocol].instance
            or container._registrations[LLMServiceProtocol].factory
        )
        llm_service = llm_resolver() if callable(llm_resolver) else llm_resolver

        if llm_service:
            return LLMSuggester(
                llm_service=llm_service,
                min_confidence=settings.min_confidence,
                timeout_seconds=settings.llm_timeout,
            )

    return None


# Helper function to get a service from the container
def get_service(service_type: Type[T]) -> T:
    """
    Get a service from the global container.

    This is a convenience function for getting services from the global container
    without having to explicitly get the container first.

    Args:
        service_type: The type of service to resolve

    Returns:
        An instance of the requested service

    Raises:
        DependencyResolutionError: If the service cannot be resolved
    """
    from . import get_container

    container = get_container()
    return container.resolve(service_type)


# Initialize the global container with default services
def initialize_container(settings: Optional[Settings] = None) -> Container:
    """
    Initialize the global container with all required services.

    This function creates a new container, configures it with all services,
    and sets it as the global container.

    Args:
        settings: Optional Settings object (creates default settings if None)

    Returns:
        The configured global container
    """
    from . import set_container

    # Create a new container
    container = Container()

    # Configure services
    configure_services(container, settings)

    # Set as global container
    set_container(container)

    return container
