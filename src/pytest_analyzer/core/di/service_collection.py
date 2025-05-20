"""
Service collection for dependency registration.

This module provides functionality to register all services and dependencies
for the pytest analyzer with the DI container. It implements a fluent builder pattern
for configuring services and handles automatic detection and initialization of
external dependencies like LLM clients.

The ServiceCollection class offers methods to:
- Register singleton, transient, and factory services
- Configure core services needed by the analyzer
- Automatically detect and configure LLM providers based on settings
- Build and finalize the dependency injection container

Example usage:
    # Create a new service collection
    services = ServiceCollection()

    # Configure core services with automatic LLM detection
    services.configure_core_services().configure_llm_services()

    # Get the configured container
    container = services.build_container()

    # Resolve a service
    analyzer = container.resolve(DIPytestAnalyzerService)
"""

# ServiceCollection class for fluent registration interface

import logging
from typing import Any, Callable, Optional, Type, TypeVar, Union

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
from .container import Container, RegistrationMode

# Type variable for generic type annotations
T = TypeVar("T")
TImpl = TypeVar("TImpl")

logger = logging.getLogger(__name__)


class ServiceCollection:
    """
    Fluent API for registering services with the DI container.

    This class provides a builder-style interface for registering services
    and configuring the DI container. It supports method chaining for a
    cleaner configuration experience and handles the detection and initialization
    of external dependencies like LLM clients.

    Key features:
    - Fluent builder pattern with method chaining
    - Service registration with different lifetimes (singleton, transient)
    - Factory method registration for complex service initialization
    - Automatic LLM client detection based on settings or environment variables
    - Provider preference and fallback handling for LLM services
    - Structured composition of the dependency tree

    Usage pattern:
    1. Create ServiceCollection instance
    2. Register services with add_* methods
    3. Configure system components with configure_* methods
    4. Build and get the container
    5. Resolve services from the container
    """

    def __init__(self):
        """Initialize a new service collection."""
        self.container = Container()

    def add_singleton(
        self, interface_type: Type[T], implementation: Union[Type[Any], Any]
    ) -> "ServiceCollection":
        """
        Register a singleton service.

        Args:
            interface_type: The interface or type to register
            implementation: The implementation type or instance

        Returns:
            Self for method chaining
        """
        self.container.register(
            interface_type, implementation, RegistrationMode.SINGLETON
        )
        return self

    def add_transient(
        self, interface_type: Type[T], implementation: Union[Type[Any], Any]
    ) -> "ServiceCollection":
        """
        Register a transient service.

        Args:
            interface_type: The interface or type to register
            implementation: The implementation type or instance

        Returns:
            Self for method chaining
        """
        self.container.register(
            interface_type, implementation, RegistrationMode.TRANSIENT
        )
        return self

    def add_factory(
        self, interface_type: Type[T], factory: Callable[[], T]
    ) -> "ServiceCollection":
        """
        Register a factory for creating service instances.

        Args:
            interface_type: The interface or type to register
            factory: Factory function for creating instances

        Returns:
            Self for method chaining
        """
        self.container.register_factory(interface_type, factory)
        return self

    def configure_core_services(self) -> "ServiceCollection":
        """
        Configure the core services needed by the pytest analyzer.

        Returns:
            Self for method chaining
        """
        # Get the settings instance
        settings = (
            self.container.resolve(Settings)
            if Settings in self._get_registrations()
            else Settings()
        )

        # Configure all services using the existing function
        configure_services(self.container, settings)
        return self

    def configure_extractors(self) -> "ServiceCollection":
        """
        Configure the extraction services.

        Returns:
            Self for method chaining
        """
        # This method doesn't need to do anything special because
        # extractors are already configured in configure_services
        return self

    def configure_llm_services(
        self, llm_client: Optional[Any] = None, override_provider: Optional[str] = None
    ) -> "ServiceCollection":
        """
        Configure LLM services with an optional specific client or provider override.

        This method handles the registration of LLM services with the container. It supports
        three operational modes:

        1. Using a provided client directly (bypassing auto-detection)
        2. Using a specific provider with override_provider (e.g., "anthropic", "openai")
        3. Using automatic detection based on settings.llm_provider with fallback capability

        The method will:
        - Attempt to detect available LLM clients if none provided directly
        - Respect provider preferences from settings.llm_provider or override_provider
        - Honor fallback settings (settings.use_fallback) when appropriate
        - Register the resulting LLM service with the container

        Supported providers:
        - anthropic: Anthropic Claude models
        - openai: OpenAI GPT models
        - azure: Azure OpenAI service
        - together: Together.ai models
        - ollama: Local Ollama deployments

        Args:
            llm_client: Optional specific LLM client to use directly (bypasses detection)
            override_provider: Optional provider name to use, overriding settings.llm_provider

        Returns:
            Self for method chaining
        """
        # Get the settings instance if available
        settings = (
            self.container.resolve(Settings)
            if Settings in self._get_registrations()
            else Settings()
        )

        # Create the LLM service components
        # Note: PromptBuilder and ResponseParser will be created inside the LLMService if needed

        # If a specific LLM client was provided, use it to create the service
        if llm_client is not None:
            try:
                # Create LLM service with the provided client
                llm_service = LLMService(
                    llm_client=llm_client,
                    timeout_seconds=settings.llm_timeout,
                )
                # Register the service
                self.container.register_instance(LLMServiceProtocol, llm_service)
                logger.info(
                    f"Registered LLM service with provided client of type: {type(llm_client).__name__}"
                )
            except Exception as e:
                logger.warning(f"Error creating LLM service with provided client: {e}")
        # Otherwise use the factory to automatically detect and create a client
        else:
            try:
                from ..llm.llm_service_factory import detect_llm_client

                # Choose the provider preference, with override taking precedence
                preferred_provider = (
                    override_provider if override_provider else settings.llm_provider
                )

                # Try to detect an LLM client with the specified provider preference
                llm_client, provider = detect_llm_client(
                    settings=settings,
                    preferred_provider=preferred_provider,
                    fallback=settings.use_fallback
                    and not override_provider,  # Only fall back if using settings provider
                )

                if llm_client:
                    # Create service with detected client
                    llm_service = LLMService(
                        llm_client=llm_client,
                        timeout_seconds=settings.llm_timeout,
                    )
                    # Register the service
                    self.container.register_instance(LLMServiceProtocol, llm_service)
                    provider_name = (
                        provider.name if hasattr(provider, "name") else str(provider)
                    )
                    logger.info(
                        f"Registered LLM service with auto-detected {provider_name} client"
                    )
                else:
                    logger.warning(
                        f"No LLM client could be detected for provider '{preferred_provider}'. Registering LLMService with no client."
                    )
                    # Register LLMService with no client if none detected
                    llm_service = LLMService(
                        llm_client=None,
                        timeout_seconds=settings.llm_timeout,
                        disable_auto_detection=True,
                    )
                    self.container.register_instance(LLMServiceProtocol, llm_service)
            except Exception as e:
                logger.warning(
                    f"Error detecting or creating LLM service: {e}. Registering LLMService with no client."
                )
                # Register LLMService with no client on error
                llm_service = LLMService(
                    llm_client=None,
                    timeout_seconds=settings.llm_timeout,  # Use settings timeout if possible
                    disable_auto_detection=True,
                )
                self.container.register_instance(LLMServiceProtocol, llm_service)

        return self

    def build_container(self) -> Container:
        """
        Build and return the configured container.

        Returns:
            The configured Container instance
        """
        return self.container

    def _get_registrations(self):
        """Get the registrations dictionary from the container."""
        return getattr(self.container, "_registrations", {})


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
        try:
            context.analyzer = container.resolve(FailureAnalyzer)
        except Exception as e:
            logger.debug(f"Could not resolve FailureAnalyzer for AnalyzerContext: {e}")
            context.analyzer = None

    if FixSuggester in container._registrations:
        try:
            context.suggester = container.resolve(FixSuggester)
        except Exception as e:
            logger.debug(f"Could not resolve FixSuggester for AnalyzerContext: {e}")
            context.suggester = None

    if FixApplier in container._registrations:
        try:
            context.fix_applier = container.resolve(FixApplier)
        except Exception as e:
            logger.debug(f"Could not resolve FixApplier for AnalyzerContext: {e}")
            context.fix_applier = None

    # Add LLM suggester if enabled
    if settings.use_llm and LLMSuggester in container._registrations:
        try:
            context.llm_suggester = container.resolve(LLMSuggester)
        except Exception as e:
            logger.debug(f"Could not resolve LLMSuggester for AnalyzerContext: {e}")
            context.llm_suggester = None

    return context


def _create_llm_service(container: Container = None) -> Optional[LLMServiceProtocol]:
    """
    Factory function to create an LLM service with automatic client detection.

    This function is designed to be used as a factory for the DI container to
    create and configure LLM services. It:

    1. Resolves settings from the container
    2. Uses the llm_service_factory module to auto-detect available LLM clients
    3. Respects provider preferences specified in settings.llm_provider
    4. Handles fallback behavior based on settings.use_fallback
    5. Creates an appropriate LLM service with the detected client
    6. Properly handles import errors and other exceptions with sensible defaults

    The function is used internally by the DI system when an LLMServiceProtocol
    is resolved from the container. The auto-detection uses both settings and
    environment variables to find API keys for different providers.

    Args:
        container: Optional container, if not provided the global container will be used

    Returns:
        A properly configured LLM service instance with detected client
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

    # Note: In the DI context, we always create the service when requested, and leave it to the
    # DIPytestAnalyzerService factory to decide whether to include it based on settings.use_llm
    # This ensures the LLMServiceProtocol is always resolvable when tests explicitly enable use_llm=True

    # Create the LLM service components as needed in the LLMService constructor

    try:
        # Attempt to detect LLM clients and configure them
        from ..llm.llm_service_factory import detect_llm_client

        # Try to detect an available LLM client with the specified provider preference
        llm_client, provider = detect_llm_client(
            settings=settings,
            preferred_provider=settings.llm_provider,
            fallback=settings.use_fallback,  # Use the fallback setting from settings
        )

        if llm_client:
            logger.info(
                f"Created LLM service with detected client type: {type(llm_client).__name__}"
            )
        else:
            logger.warning("No LLM client detected, creating service with no client")

        # Create service with detected client if available, otherwise None
        return LLMService(
            llm_client=llm_client,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=(llm_client is None),
        )
    except ImportError:
        # If the factory module isn't available, continue with None client
        logger.debug(
            "LLM service factory not available, creating service with no client"
        )
        return LLMService(
            llm_client=None,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=True,
        )
    except Exception as e:
        logger.warning(
            f"Error creating LLM service: {e}. Creating service with no client."
        )
        # Fallback to creating with no client, respecting settings timeout
        return LLMService(
            llm_client=None,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=True,
        )


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
