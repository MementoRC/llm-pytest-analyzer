"""
Dependency Injection Container implementation.

This module provides a container for registering and resolving dependencies
with support for various registration modes and lifecycle management.
"""

import enum
import inspect
import logging
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
    get_type_hints,
)

from ..errors import DependencyResolutionError

logger = logging.getLogger(__name__)

# Type variable for generic type annotations
T = TypeVar("T")
TImpl = TypeVar("TImpl")
TKey = TypeVar("TKey")


class RegistrationMode(enum.Enum):
    """
    Enumeration of registration modes for the dependency injection container.

    These modes control how instances are created and managed:
    - SINGLETON: A single instance is created and reused for all resolutions
    - TRANSIENT: A new instance is created for each resolution
    - FACTORY: A factory function is used to create instances
    - SCOPED: A single instance is created per scope (similar to per-request in web apps)
    """

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    FACTORY = "factory"
    SCOPED = "scoped"


class Registration(Generic[T]):
    """
    Registration entry in the dependency injection container.

    This class holds the information needed to create and manage instances
    of a registered dependency, including its implementation type/instance,
    registration mode, and factory function (if applicable).
    """

    def __init__(
        self,
        implementation: Optional[Union[Type[T], T]] = None,
        mode: RegistrationMode = RegistrationMode.SINGLETON,
        factory: Optional[Callable[[], T]] = None,
    ):
        """
        Initialize a new registration entry.

        Args:
            implementation: The implementation type or instance
            mode: The registration mode (singleton, transient, factory)
            factory: Optional factory function for creating instances
        """
        self.implementation = implementation
        self.mode = mode
        self.factory = factory
        self.instance: Optional[T] = None

        # If implementation is already an instance and mode is singleton, store it
        if (
            mode == RegistrationMode.SINGLETON
            and implementation is not None
            and not isinstance(implementation, type)
        ):
            self.instance = cast("T", implementation)


class Scope:
    """
    A scope for scoped registrations in the container.

    Scopes provide a way to create per-request or per-operation
    instances without creating a new object on every resolution.
    """

    def __init__(self, parent_container: "Container"):
        """
        Initialize a new scope.

        Args:
            parent_container: The parent container creating this scope
        """
        self._parent = parent_container
        self._instances: Dict[Type, Any] = {}
        self._disposed = False

    def resolve(self, type_: Type[T]) -> T:
        """
        Resolve a scoped dependency from this scope.

        Args:
            type_: The type to resolve

        Returns:
            The resolved instance

        Raises:
            DependencyResolutionError: If the scope has been disposed
        """
        if self._disposed:
            raise DependencyResolutionError("Attempt to resolve from a disposed scope")

        # If we have the instance in this scope, return it
        if type_ in self._instances:
            return self._instances[type_]

        # Otherwise create and store it
        instance = self._parent._create_scoped_instance(type_, self)
        self._instances[type_] = instance
        return instance

    def dispose(self) -> None:
        """
        Dispose of this scope and all instances it contains.

        This will call __del__ on all instances that support it.
        """
        if self._disposed:
            return

        # Clear all instances, calling dispose if they support it
        for instance in self._instances.values():
            if hasattr(instance, "__del__"):
                try:
                    instance.__del__()
                except Exception as e:
                    logger.warning(f"Error disposing instance: {e}")

        self._instances.clear()
        self._disposed = True


class Container:
    """
    Dependency Injection Container.

    This container manages the registration and resolution of dependencies,
    supporting various registration modes and lifecycle management.
    """

    def __init__(self, parent: Optional["Container"] = None):
        """
        Initialize a new dependency injection container.

        Args:
            parent: Optional parent container for hierarchical resolution
        """
        self._registrations: Dict[Type, Registration] = {}
        self._parent = parent
        self._current_scope: Optional[Scope] = None

    def register(
        self,
        interface_type: Type[T],
        implementation: Union[Type[TImpl], TImpl],
        mode: RegistrationMode = RegistrationMode.SINGLETON,
    ) -> None:
        """
        Register a dependency with the container.

        Args:
            interface_type: The interface or type to register
            implementation: The implementation type or instance
            mode: The registration mode (singleton, transient, factory, scoped)

        Raises:
            ConfigurationError: If registration conflicts with existing entries
        """
        if interface_type in self._registrations:
            logger.warning(f"Registration for {interface_type.__name__} is being overridden")

        # Create and store the registration
        registration = Registration(implementation=implementation, mode=mode)
        self._registrations[interface_type] = registration

        logger.debug(
            f"Registered {interface_type.__name__} with "
            f"{implementation.__name__ if isinstance(implementation, type) else type(implementation).__name__} "
            f"using mode {mode.value}"
        )

    def register_singleton(
        self, interface_type: Type[T], implementation: Union[Type[TImpl], TImpl]
    ) -> None:
        """
        Register a singleton dependency with the container.

        Args:
            interface_type: The interface or type to register
            implementation: The implementation type or instance
        """
        self.register(interface_type, implementation, RegistrationMode.SINGLETON)

    def register_transient(
        self, interface_type: Type[T], implementation: Union[Type[TImpl], TImpl]
    ) -> None:
        """
        Register a transient dependency with the container.

        Args:
            interface_type: The interface or type to register
            implementation: The implementation type or instance
        """
        self.register(interface_type, implementation, RegistrationMode.TRANSIENT)

    def register_scoped(
        self, interface_type: Type[T], implementation: Union[Type[TImpl], TImpl]
    ) -> None:
        """
        Register a scoped dependency with the container.

        Args:
            interface_type: The interface or type to register
            implementation: The implementation type or instance
        """
        self.register(interface_type, implementation, RegistrationMode.SCOPED)

    def register_factory(self, interface_type: Type[T], factory: Callable[[], T]) -> None:
        """
        Register a factory function for creating instances.

        Args:
            interface_type: The interface or type to register
            factory: The factory function for creating instances

        Raises:
            ConfigurationError: If registration conflicts with existing entries
        """
        if interface_type in self._registrations:
            logger.warning(f"Registration for {interface_type.__name__} is being overridden")

        # Create and store the registration
        registration = Registration(
            implementation=None, mode=RegistrationMode.FACTORY, factory=factory
        )
        self._registrations[interface_type] = registration

        logger.debug(f"Registered factory for {interface_type.__name__}")

    def register_instance(self, interface_type: Type[T], instance: T) -> None:
        """
        Register an existing instance with the container.

        This is a convenience method equivalent to registering with SINGLETON mode
        but explicitly providing an instance instead of a type.

        Args:
            interface_type: The interface or type to register
            instance: The instance to register
        """
        self.register(interface_type, instance, RegistrationMode.SINGLETON)

    def register_many(
        self,
        implementations: Dict[Type, Union[Type, Any, Callable[[], Any]]],
        mode: RegistrationMode = RegistrationMode.SINGLETON,
    ) -> None:
        """
        Register multiple dependencies at once.

        Args:
            implementations: A dictionary mapping interfaces to implementations
            mode: The registration mode to use for all registrations
        """
        for interface_type, implementation in implementations.items():
            if callable(implementation) and not isinstance(implementation, type):
                # Register as a factory if it's a callable but not a class
                self.register_factory(interface_type, implementation)
            else:
                # Register as a regular dependency otherwise
                self.register(interface_type, implementation, mode)

    def create_scope(self) -> Scope:
        """
        Create a new scope for scoped registrations.

        Scopes allow creating per-request or per-operation instances
        that are shared within the scope but not between scopes.

        Returns:
            A new Scope object
        """
        return Scope(self)

    def begin_scope(self) -> Scope:
        """
        Begin a new scope and set it as the current scope.

        Returns:
            The new Scope object
        """
        self._current_scope = self.create_scope()
        return self._current_scope

    def end_scope(self) -> None:
        """
        End the current scope and dispose of all its instances.
        """
        if self._current_scope:
            self._current_scope.dispose()
            self._current_scope = None

    def resolve(self, interface_type: Type[T]) -> T:
        """
        Resolve a dependency from the container.

        Args:
            interface_type: The interface or type to resolve

        Returns:
            An instance of the requested type

        Raises:
            DependencyResolutionError: If the dependency cannot be resolved
        """
        # Check if the type is registered in this container
        if interface_type in self._registrations:
            registration = self._registrations[interface_type]

            # Handle based on registration mode
            if registration.mode == RegistrationMode.SINGLETON:
                return self._resolve_singleton(interface_type, registration)

            if registration.mode == RegistrationMode.TRANSIENT:
                return self._resolve_transient(interface_type, registration)

            if registration.mode == RegistrationMode.FACTORY:
                return self._resolve_factory(interface_type, registration)

            if registration.mode == RegistrationMode.SCOPED:
                return self._resolve_scoped(interface_type, registration)

            # Should never reach here, but added for completeness
            raise DependencyResolutionError(
                f"Unknown registration mode for {interface_type.__name__}"
            )

        # Type is not registered in this container
        # Try to resolve from parent container if available
        if self._parent is not None:
            try:
                return self._parent.resolve(interface_type)
            except DependencyResolutionError:
                # Fall through to the error below if parent can't resolve
                pass

        # No registration found in this container or parents
        raise DependencyResolutionError(f"No registration found for {interface_type.__name__}")

    def _resolve_singleton(self, interface_type: Type[T], registration: Registration[T]) -> T:
        """
        Resolve a singleton dependency.

        Args:
            interface_type: The interface or type to resolve
            registration: The registration entry

        Returns:
            The singleton instance
        """
        # Return existing instance if available
        if registration.instance is not None:
            return cast("T", registration.instance)

        # Create singleton instance if not already created
        if isinstance(registration.implementation, type):
            try:
                # Create instance using constructor injection
                instance = self._create_instance(cast("Type[T]", registration.implementation))
            except Exception as e:
                raise DependencyResolutionError(
                    f"Failed to create instance of {interface_type.__name__}: {str(e)}"
                ) from e

            # Store for future resolutions
            registration.instance = instance
            return instance
        # If implementation is already an instance, store and return it
        instance = cast("T", registration.implementation)
        registration.instance = instance
        return instance

    def _resolve_transient(self, interface_type: Type[T], registration: Registration[T]) -> T:
        """
        Resolve a transient dependency.

        Args:
            interface_type: The interface or type to resolve
            registration: The registration entry

        Returns:
            A new instance on each call
        """
        # Create new instance each time
        if isinstance(registration.implementation, type):
            try:
                # Create instance using constructor injection
                return self._create_instance(cast("Type[T]", registration.implementation))
            except Exception as e:
                raise DependencyResolutionError(
                    f"Failed to create instance of {interface_type.__name__}: {str(e)}"
                ) from e
        else:
            # Return the instance directly (not typical for transient)
            return cast("T", registration.implementation)

    def _resolve_factory(self, interface_type: Type[T], registration: Registration[T]) -> T:
        """
        Resolve a dependency using its factory function.

        Args:
            interface_type: The interface or type to resolve
            registration: The registration entry

        Returns:
            An instance created by the factory
        """
        # Use factory to create instance
        if registration.factory is None:
            raise DependencyResolutionError(f"Factory is not defined for {interface_type.__name__}")

        try:
            return registration.factory()
        except Exception as e:
            raise DependencyResolutionError(
                f"Factory failed to create instance of {interface_type.__name__}: {str(e)}"
            ) from e

    def _resolve_scoped(self, interface_type: Type[T], registration: Registration[T]) -> T:
        """
        Resolve a scoped dependency.

        Args:
            interface_type: The interface or type to resolve
            registration: The registration entry

        Returns:
            An instance scoped to the current scope

        Raises:
            DependencyResolutionError: If no active scope is available
        """
        # Need an active scope for scoped dependencies
        if self._current_scope is None:
            raise DependencyResolutionError(
                f"Cannot resolve scoped dependency {interface_type.__name__} without an active scope"
            )

        # Delegate to the current scope
        return self._current_scope.resolve(interface_type)

    def _create_scoped_instance(self, type_: Type[T], scope: Scope) -> T:
        """
        Create an instance for a scoped dependency.

        Args:
            type_: The type to create
            scope: The scope requesting the instance

        Returns:
            A new instance for the scope

        Raises:
            DependencyResolutionError: If the type is not registered or not scoped
        """
        # Check if the type is registered
        if type_ not in self._registrations:
            raise DependencyResolutionError(
                f"No registration found for scoped type {type_.__name__}"
            )

        registration = self._registrations[type_]

        # Verify it's a scoped registration
        if registration.mode != RegistrationMode.SCOPED:
            raise DependencyResolutionError(f"Type {type_.__name__} is not registered as scoped")

        # Create the instance
        if isinstance(registration.implementation, type):
            try:
                # Create instance using constructor injection
                # Use a temporary scope as the current scope for dependency resolution
                old_scope = self._current_scope
                self._current_scope = scope
                try:
                    return self._create_instance(cast("Type[T]", registration.implementation))
                finally:
                    # Restore the original scope
                    self._current_scope = old_scope
            except Exception as e:
                raise DependencyResolutionError(
                    f"Failed to create scoped instance of {type_.__name__}: {str(e)}"
                ) from e
        else:
            # Return the instance directly (not typical for scoped)
            return cast("T", registration.implementation)

    def _create_instance(self, implementation_type: Type[T]) -> T:
        """
        Create an instance of the specified type using constructor injection.

        Args:
            implementation_type: The type to instantiate

        Returns:
            An instance of the specified type

        Raises:
            DependencyResolutionError: If the instance cannot be created
        """
        # Quick check - if it's object's __init__, just create the instance directly
        # This handles the case where the class doesn't define its own __init__
        if implementation_type.__init__ is object.__init__:
            return implementation_type()

        try:
            # Get constructor and its parameters
            signature = inspect.signature(implementation_type.__init__)

            # Skip 'self' parameter
            parameters = list(signature.parameters.items())[1:]

            # No parameters, create directly
            if not parameters:
                return implementation_type()

            # Get type hints for constructor parameters
            try:
                type_hints = get_type_hints(implementation_type.__init__)
            except TypeError:
                # This can happen with protocol classes which are not fully typed
                # Just create an instance directly in this case
                return implementation_type()

            # Prepare arguments for constructor
            kwargs = {}
            for name, parameter in parameters:
                # Skip parameters with default values
                if parameter.default != inspect.Parameter.empty:
                    continue

                # Get parameter type
                if name not in type_hints:
                    # If no type hint, we can't inject - just create directly if possible
                    try:
                        return implementation_type()
                    except Exception as e:
                        raise DependencyResolutionError(
                            f"Cannot create instance of {implementation_type.__name__}: "
                            f"missing type hint for parameter '{name}' and direct instantiation failed: {str(e)}"
                        ) from e

                param_type = type_hints[name]

                # Resolve dependency
                try:
                    kwargs[name] = self.resolve(param_type)
                except DependencyResolutionError as e:
                    raise DependencyResolutionError(
                        f"Cannot resolve dependency for parameter '{name}' in {implementation_type.__name__} "
                        f"constructor: {str(e)}"
                    ) from e

            # Create instance with resolved dependencies
            return implementation_type(**kwargs)

        except Exception as e:
            if not isinstance(e, DependencyResolutionError):
                raise DependencyResolutionError(
                    f"Failed to create instance of {implementation_type.__name__}: {str(e)}"
                ) from e
            raise
