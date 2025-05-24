"""
Dependency Injection decorator module.

This module provides decorators for registering components with the DI container,
offering a clean and declarative syntax for dependency registration.
"""

import functools
import inspect
from typing import Callable, Optional, Type, TypeVar, Union, get_type_hints

from ..errors import DependencyResolutionError
from .container import Container, RegistrationMode

T = TypeVar("T")


def register(
    container: Container,
    interface_type: Optional[Type[T]] = None,
    mode: RegistrationMode = RegistrationMode.SINGLETON,
) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class with the DI container.

    This decorator allows registering a class with the container using
    a clean, declarative syntax. If the interface type is not specified,
    the class itself is used as the interface.

    Args:
        container: The DI container to register with
        interface_type: The interface or base type (optional)
        mode: The registration mode (singleton, transient, factory)

    Returns:
        A decorator function that registers the class and returns it unchanged

    Examples:
        @register(container, IService)
        class ServiceImpl(IService):
            ...

        # Or using the class itself as the interface:
        @register(container)
        class Service:
            ...
    """

    def decorator(cls: Type[T]) -> Type[T]:
        # Use the class itself as the interface if none specified
        actual_interface = interface_type or cls

        # Register with the container
        container.register(actual_interface, cls, mode)

        # Return the class unchanged
        return cls

    return decorator


def singleton(
    container: Container, interface_type: Optional[Type[T]] = None
) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as a singleton with the DI container.

    Args:
        container: The DI container to register with
        interface_type: The interface or base type (optional)

    Returns:
        A decorator function that registers the class as a singleton
    """
    return register(container, interface_type, RegistrationMode.SINGLETON)


def transient(
    container: Container, interface_type: Optional[Type[T]] = None
) -> Callable[[Type[T]], Type[T]]:
    """
    Decorator to register a class as transient with the DI container.

    Args:
        container: The DI container to register with
        interface_type: The interface or base type (optional)

    Returns:
        A decorator function that registers the class as transient
    """
    return register(container, interface_type, RegistrationMode.TRANSIENT)


def factory(
    container: Container, interface_type: Type[T]
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to register a factory function with the DI container.

    Args:
        container: The DI container to register with
        interface_type: The interface or type the factory produces

    Returns:
        A decorator function that registers the factory function

    Examples:
        @factory(container, IService)
        def create_service() -> IService:
            return ServiceImpl()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        # Register the factory with the container
        container.register_factory(interface_type, func)

        # Return the function unchanged
        return func

    return decorator


def inject(
    container_or_func: Union[Container, Callable] = None,
) -> Union[Callable[[Callable], Callable], Callable]:
    """
    Decorator to inject dependencies into function or method parameters.

    This decorator allows automatic injection of dependencies into function
    or method parameters based on their type annotations, without requiring
    explicit container.resolve() calls.

    Args:
        container_or_func: Optional container to use for injection.
                          If not provided, the global container will be used.
                          Can also be the function to decorate when used without arguments.

    Returns:
        A wrapped function that will have its dependencies injected

    Examples:
        # Using the global container:
        @inject
        def process_data(repository: IRepository, logger: ILogger):
            ...

        # Using a specific container:
        @inject(my_container)
        def process_data(repository: IRepository, logger: ILogger):
            ...

        # Call without passing dependencies:
        process_data()  # dependencies will be injected automatically
    """
    # Detect if called with or without arguments
    if container_or_func is None:
        # Called with no args like @inject
        # Return a decorator that will use the global container
        return lambda func: _create_inject_wrapper(func, None)
    if isinstance(container_or_func, Container):
        # Called with a container like @inject(container)
        # Return a decorator that will use the provided container
        return lambda func: _create_inject_wrapper(func, container_or_func)
    # Called like @inject without parentheses
    # container_or_func is actually the function to decorate
    return _create_inject_wrapper(container_or_func, None)


def _create_inject_wrapper(func: Callable, container: Optional[Container]) -> Callable:
    """
    Create a wrapper function that injects dependencies.

    Args:
        func: The function to wrap
        container: Optional explicit container to use

    Returns:
        A wrapped function that will have its dependencies injected
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Determine which container to use
        if container is None:
            # Import here to avoid circular imports
            from .__init__ import get_container

            # Use the global container if none specified
            container_to_use = get_container()
        else:
            # Use the explicitly provided container
            container_to_use = container

        try:
            # Get type hints excluding return type
            hints = get_type_hints(func)
            if "return" in hints:
                del hints["return"]

            # Get the signature to know which parameters need injection
            sig = inspect.signature(func)
            params = sig.parameters

            # Prepare the arguments to inject
            injected_kwargs = {}

            # Skip 'self' or 'cls' if this is a method
            param_items = list(params.items())
            if args and len(param_items) > 0:
                # If we have positional args and parameters, skip self/cls
                param_items = param_items[len(args) :]

            # Check each parameter
            for name, param in param_items:
                # Skip if already provided in kwargs
                if name in kwargs:
                    continue

                # Only inject parameters with type hints
                if name in hints:
                    param_type = hints[name]

                    # Inject the dependency if it has no default or default is None
                    if param.default is inspect.Parameter.empty or param.default is None:
                        try:
                            injected_kwargs[name] = container_to_use.resolve(param_type)
                        except Exception:
                            # If resolution fails and parameter has default, use that
                            if param.default is not inspect.Parameter.empty:
                                pass  # Just skip it, the default will be used
                            else:
                                # Re-raise if there's no default
                                raise

            # Combine injected kwargs with provided kwargs (provided take precedence)
            combined_kwargs = {**injected_kwargs, **kwargs}

            # Call the original function with args and combined kwargs
            return func(*args, **combined_kwargs)
        except Exception as e:
            raise DependencyResolutionError(
                f"Failed to inject dependencies for {func.__name__}: {str(e)}"
            ) from e

    return wrapper
