import functools
import logging
from contextlib import contextmanager
from typing import Any, Callable, Generator, List, Optional, Tuple, Type, TypeVar

from pytest_analyzer.core.interfaces.errors import BaseError

# Default logger for utilities if no specific logger is provided
module_logger = logging.getLogger(__name__)

_ET = TypeVar("_ET", bound=Exception)  # Exception type variable
_R = TypeVar("_R")  # Return type variable for error_handler
_IT = TypeVar("_IT")  # Item type for batch_operation
_RT = TypeVar("_RT")  # Result type for batch_operation


@contextmanager
def error_context(
    operation_name: str,
    logger: logging.Logger,
    error_type: Type[_ET],
    reraise: bool = True,
) -> Generator[None, None, None]:
    """
    Synchronous context manager for consistent error handling.
    Wraps a block of code, logging the operation's start and end.
    Catches exceptions, logs them, and optionally re-raises them, possibly wrapped.

    Args:
        operation_name: Name of the operation for logging.
        logger: Logger instance to use for logging.
        error_type: The type of exception to raise if an error is caught and wrapped.
        reraise: If True (default), exceptions are re-raised. If False, they are logged and suppressed.
    """
    logger.info(f"Starting operation: {operation_name}")
    try:
        yield
        logger.info(f"Successfully completed operation: {operation_name}")
    except Exception as e:
        logger.error(f"Error during operation '{operation_name}': {e}", exc_info=True)
        if reraise:
            if isinstance(e, error_type):
                raise  # Re-raise if it's already the target type or its subclass

            # Check if error_type is a subclass of BaseError to pass original_exception
            if issubclass(error_type, BaseError):
                # Pass the operation name as the primary message for BaseError.
                # BaseError's __str__ method is expected to append the original_exception.
                message_prefix = f"{operation_name} failed"
                raise error_type(message_prefix, original_exception=e) from e
            else:
                # For other exception types, include the original error string in the message.
                full_message = f"{operation_name} failed: {e}"
                raise error_type(full_message) from e
        # If not reraise, the exception is suppressed after logging.


def error_handler(
    operation_name: str,
    error_type: Type[_ET],
    reraise: bool = True,
    logger: Optional[logging.Logger] = None,
) -> Callable[[Callable[..., _R]], Callable[..., Optional[_R]]]:
    """
    Decorator for consistent error handling in synchronous functions.
    Logs function call, catches exceptions, logs them, and optionally re-raises.

    Args:
        operation_name: Name of the operation for logging.
        error_type: The type of exception to raise if an error is caught and wrapped.
        reraise: If True (default), exceptions are re-raised. If False, they are logged
                 and suppressed (function will return None in case of error).
        logger: Optional logger instance. Defaults to a module-level logger.

    Returns:
        A decorator that wraps the function with error handling logic.
    """
    effective_logger = logger if logger else module_logger

    def decorator(func: Callable[..., _R]) -> Callable[..., Optional[_R]]:
        @functools.wraps(func)
        def wrapper(
            *args: Any, **kwargs: Any
        ) -> Optional[_R]:  # Return type can be None if reraise is False
            effective_logger.info(
                f"Calling function '{func.__name__}' for operation: {operation_name}"
            )
            try:
                result = func(*args, **kwargs)
                effective_logger.info(
                    f"Function '{func.__name__}' for operation '{operation_name}' completed successfully."
                )
                return result
            except Exception as e:
                effective_logger.error(
                    f"Error in function '{func.__name__}' during operation '{operation_name}': {e}",
                    exc_info=True,
                )
                if reraise:
                    if isinstance(e, error_type):
                        raise  # Re-raise if it's already the target type or its subclass

                    if issubclass(error_type, BaseError):
                        # Pass a prefix message for BaseError.
                        # BaseError's __str__ is expected to append original_exception.
                        message_prefix = f"Operation '{operation_name}' (function: {func.__name__}) failed"
                        raise error_type(message_prefix, original_exception=e) from e
                    else:
                        # For other exception types, include the original error string in the message.
                        full_message = f"Operation '{operation_name}' (function: {func.__name__}) failed: {e}"
                        raise error_type(full_message) from e
                else:
                    # If not reraising, and function is expected to return something,
                    # it will return None by default.
                    return None

        return wrapper

    return decorator


def batch_operation(
    items: List[_IT],
    operation: Callable[[_IT], _RT],
    operation_name: str,
    continue_on_error: bool = True,
    logger: Optional[logging.Logger] = None,
) -> Tuple[List[_RT], List[Tuple[_IT, Exception]]]:
    """
    Processes a list of items synchronously, handling errors for each item.

    Args:
        items: A list of items to process.
        operation: A synchronous function to apply to each item.
        operation_name: Name of the batch operation for logging.
        continue_on_error: If True (default), continues processing other items after an error.
                           If False, stops on the first error.
        logger: Optional logger instance. Defaults to a module-level logger.

    Returns:
        A tuple containing two lists:
        - The first list contains the results of successful operations.
        - The second list contains tuples of (item, exception_instance) for failed operations.
    """
    effective_logger = logger if logger else module_logger
    successful_results: List[_RT] = []
    errors: List[Tuple[_IT, Exception]] = []

    effective_logger.info(
        f"Starting batch operation: {operation_name} for {len(items)} items."
    )

    for index, item in enumerate(items):
        item_repr = str(
            item
        )  # To avoid issues if item's str() fails, though unlikely for typical inputs
        effective_logger.debug(
            f"Processing item {index + 1}/{len(items)} ('{item_repr}') for batch operation '{operation_name}'."
        )
        try:
            result = operation(item)
            successful_results.append(result)
            effective_logger.debug(
                f"Successfully processed item '{item_repr}' in '{operation_name}'."
            )
        except Exception as e:
            effective_logger.error(
                f"Error processing item '{item_repr}' (item {index + 1}/{len(items)}) "
                f"in batch operation '{operation_name}': {e}",
                exc_info=True,
            )
            errors.append((item, e))
            if not continue_on_error:
                effective_logger.warning(
                    f"Batch operation '{operation_name}' stopped early due to error on item '{item_repr}' "
                    f"(continue_on_error=False)."
                )
                break

    effective_logger.info(
        f"Batch operation '{operation_name}' completed. "
        f"Successful: {len(successful_results)}, Failed: {len(errors)}."
    )
    return successful_results, errors
