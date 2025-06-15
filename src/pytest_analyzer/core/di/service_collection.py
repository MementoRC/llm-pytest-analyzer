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
from ..analysis.fix_applier_adapter import FixApplierAdapter
from ..analysis.fix_suggester import FixSuggester
from ..analysis.llm_suggester import LLMSuggester
from ..analyzer_service import PytestAnalyzerService
from ..analyzer_service_di import DIPytestAnalyzerService
from ..environment.detector import EnvironmentManagerDetector
from ..environment.protocol import EnvironmentManager
from ..factories.analyzer_factory import create_llm_service, create_llm_suggester
from ..interfaces.protocols import Applier, Orchestrator
from ..llm.llm_service_protocol import LLMServiceProtocol
from ..orchestration.analyzer_orchestrator import AnalyzerOrchestrator
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

        Args:
            llm_client: Optional pre-configured LLM client to use
            override_provider: Optional provider name to override settings

        Returns:
            Self for method chaining
        """
        # Register the LLM service factory with the specific parameters
        if llm_client is not None:
            # Direct client provided - create factory that returns LLMService with this client
            self.container.register_factory(
                LLMServiceProtocol,
                lambda: _create_llm_service_with_client(self.container, llm_client),
            )
        elif override_provider is not None:
            # Provider override - create factory that uses the override provider
            self.container.register_factory(
                LLMServiceProtocol,
                lambda: _create_llm_service_with_provider(
                    self.container, override_provider
                ),
            )
        else:
            # Default behavior - use existing factory from configure_services
            # This is already registered in configure_services, but register it explicitly if not present
            if LLMServiceProtocol not in self._get_registrations():
                self.container.register_factory(
                    LLMServiceProtocol, lambda: _create_llm_service(self.container)
                )

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
        container.register_factory(Settings, lambda: Settings())

    settings_instance = container.resolve(Settings)

    # Register utility services
    container.register_factory(
        PathResolver, lambda: PathResolver(settings_instance.project_root)
    )

    # Register EnvironmentManagerDetector and EnvironmentManager
    container.register_factory(
        EnvironmentManagerDetector,
        lambda: EnvironmentManagerDetector(
            project_path=container.resolve(PathResolver).project_root
        ),
    )
    container.register_factory(
        EnvironmentManager,  # Registering the protocol
        lambda: container.resolve(EnvironmentManagerDetector).get_active_manager(),
    )

    # Register analysis components
    container.register_singleton(FailureAnalyzer, FailureAnalyzer)
    container.register_singleton(FixSuggester, FixSuggester)

    # Register FixApplier and its adapter
    container.register_singleton(FixApplier, FixApplier)
    container.register_factory(
        Applier, lambda: FixApplierAdapter(fix_applier=container.resolve(FixApplier))
    )

    # Register LLM components using factories
    container.register_factory(
        LLMServiceProtocol, lambda: create_llm_service(container)
    )
    container.register_factory(LLMSuggester, lambda: create_llm_suggester(container))

    # Register Orchestrator
    container.register_factory(
        Orchestrator,
        lambda: AnalyzerOrchestrator(
            path_resolver=container.resolve(PathResolver),
            settings=settings_instance,
            llm_suggester=container.resolve(LLMSuggester),
        ),
    )

    # Register main service
    container.register_factory(
        PytestAnalyzerService,
        lambda: PytestAnalyzerService(
            settings=settings_instance,
            path_resolver=container.resolve(PathResolver),
            orchestrator=container.resolve(Orchestrator),
            fix_applier=container.resolve(Applier),
        ),
    )

    # Register state machine for backward compatibility - but don't auto-resolve due to complex dependencies
    # The state machine will be created manually in tests that need it

    # Register DI service for backward compatibility
    container.register_factory(
        DIPytestAnalyzerService,
        lambda: DIPytestAnalyzerService(
            settings=settings_instance,
            path_resolver=container.resolve(PathResolver),
            state_machine=None,  # Don't auto-resolve state machine due to complex dependencies
            llm_service=container.resolve(LLMServiceProtocol)
            if settings_instance.use_llm
            else None,
        ),
    )

    return container


def _create_llm_service_with_client(
    container: Container, llm_client: Any
) -> LLMServiceProtocol:
    """
    Create an LLM service with a specific client.

    Args:
        container: The DI container
        llm_client: The pre-configured LLM client to use

    Returns:
        LLM service instance with the specified client
    """
    from ..llm.backward_compat import LLMService

    try:
        settings = container.resolve(Settings)
    except Exception:
        # If settings not available, create default settings
        settings = Settings()

    return LLMService(
        llm_client=llm_client,
        timeout_seconds=settings.llm_timeout,
        disable_auto_detection=True,  # We have a specific client, no need for auto-detection
    )


def _create_llm_service_with_provider(
    container: Container, override_provider: str
) -> LLMServiceProtocol:
    """
    Create an LLM service with a provider override.

    Args:
        container: The DI container
        override_provider: The provider name to use (e.g., "anthropic", "openai")

    Returns:
        LLM service instance configured with the specified provider
    """
    from ..llm.backward_compat import LLMService

    try:
        settings = container.resolve(Settings)
    except Exception:
        # If settings not available, create default settings
        settings = Settings()

    try:
        from ..llm.llm_service_factory import detect_llm_client

        llm_client, provider = detect_llm_client(
            settings=settings,
            preferred_provider=override_provider,
            fallback=settings.use_fallback,
        )

        if llm_client:
            logger.info(
                f"Created LLM service with provider override '{override_provider}': {type(llm_client).__name__}"
            )
        else:
            logger.warning(
                f"No LLM client detected for provider '{override_provider}', creating service with no client."
            )

        return LLMService(
            llm_client=llm_client,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=(llm_client is None),
        )
    except ImportError:
        logger.debug(
            "LLM service factory not available, creating service with no client."
        )
        return LLMService(
            llm_client=None,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=True,
        )
    except Exception as e:
        logger.warning(
            f"Error creating LLM service with provider '{override_provider}': {e}. Creating service with no client."
        )
        return LLMService(
            llm_client=None,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=True,
        )


def _create_llm_service(container: Container) -> LLMServiceProtocol:
    """
    Create an LLM service using container resolution (for backward compatibility).

    Args:
        container: The DI container

    Returns:
        LLM service instance
    """
    from ..llm.backward_compat import LLMService

    try:
        settings = container.resolve(Settings)
    except Exception:
        # If settings not available, create default settings
        settings = Settings()

    # Always try LLM detection for default case (not fallback)
    if not settings.use_llm:
        return LLMService(
            llm_client=None,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=True,
        )

    try:
        from ..llm.llm_service_factory import detect_llm_client

        llm_client, provider = detect_llm_client(
            settings=settings,
            preferred_provider=settings.llm_provider,
            fallback=settings.use_fallback,
        )

        if llm_client:
            logger.info(
                f"Created LLM service with detected client: {type(llm_client).__name__}"
            )
        else:
            logger.warning("No LLM client detected, creating service with no client.")

        return LLMService(
            llm_client=llm_client,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=(llm_client is None),
        )
    except ImportError:
        logger.debug(
            "LLM service factory not available, creating service with no client."
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
        return LLMService(
            llm_client=None,
            timeout_seconds=settings.llm_timeout,
            disable_auto_detection=True,
        )


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
