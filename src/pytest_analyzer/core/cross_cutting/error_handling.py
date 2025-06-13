import functools
import logging
import time
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Generator, List, Optional, Tuple, Type, TypeVar

from pytest_analyzer.core.errors import BaseError as NewBaseError
from pytest_analyzer.core.errors import (
    CircuitBreakerOpenError,
    RetryError,
)
from pytest_analyzer.core.interfaces.errors import BaseError

# Default logger for utilities if no specific logger is provided
module_logger = logging.getLogger(__name__)

_ET = TypeVar("_ET", bound=Exception)  # Exception type variable
_R = TypeVar("_R")  # Return type variable for error_handler
_IT = TypeVar("_IT")  # Item type for batch_operation
_RT = TypeVar("_RT")  # Result type for batch_operation


class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """
    Implements the Circuit Breaker pattern to prevent repeated calls to a failing service.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: int = 60,
        half_open_attempts: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_attempts = half_open_attempts
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_success_count = 0

    @property
    def state(self) -> CircuitBreakerState:
        if (
            self._state == CircuitBreakerState.OPEN
            and self._last_failure_time is not None
            and (time.monotonic() - self._last_failure_time) > self.reset_timeout
        ):
            self._state = CircuitBreakerState.HALF_OPEN
            self._half_open_success_count = 0
        return self._state

    def record_failure(self) -> None:
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._open_circuit()
        else:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._open_circuit()

    def record_success(self) -> None:
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._half_open_success_count += 1
            if self._half_open_success_count >= self.half_open_attempts:
                self._reset()
        else:
            self._reset()

    def _open_circuit(self) -> None:
        self._state = CircuitBreakerState.OPEN
        self._last_failure_time = time.monotonic()

    def _reset(self) -> None:
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_success_count = 0

    def can_execute(self) -> bool:
        return self.state in [CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN]


def circuit_breaker(
    breaker: CircuitBreaker, logger: Optional[logging.Logger] = None
) -> Callable[[Callable[..., _R]], Callable[..., _R]]:
    """Decorator to apply circuit breaker logic to a function."""
    effective_logger = logger or module_logger

    def decorator(func: Callable[..., _R]) -> Callable[..., _R]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> _R:
            if not breaker.can_execute():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open for {func.__name__}"
                )
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                effective_logger.warning(
                    f"Circuit breaker recorded failure for {func.__name__}: {e}"
                )
                breaker.record_failure()
                raise

        return wrapper

    return decorator


def retry(
    attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    handled_exceptions: Type[Exception] = Exception,
    logger: Optional[logging.Logger] = None,
) -> Callable[[Callable[..., _R]], Callable[..., _R]]:
    """Decorator for retrying a function with exponential backoff."""
    effective_logger = logger or module_logger

    def decorator(func: Callable[..., _R]) -> Callable[..., _R]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> _R:
            current_delay = delay
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except handled_exceptions as e:
                    if attempt == attempts:
                        raise RetryError(
                            f"Operation '{func.__name__}' failed after {attempts} attempts.",
                            context={"last_error": str(e)},
                            original_exception=e,
                        ) from e
                    effective_logger.warning(
                        f"Attempt {attempt}/{attempts} for '{func.__name__}' failed: {e}. "
                        f"Retrying in {current_delay:.2f} seconds."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            # This part should be unreachable, but linters might complain.
            raise RuntimeError("Retry logic finished without returning or raising.")

        return wrapper

    return decorator


@contextmanager
def error_context(
    operation_name: str,
    logger: logging.Logger,
    error_type: Type[Exception],
    reraise: bool = True,
) -> Generator[None, None, None]:
    """Synchronous context manager for consistent error handling."""
    logger.info(f"Starting operation: {operation_name}")
    try:
        yield
        logger.info(f"Successfully completed operation: {operation_name}")
    except Exception as e:
        logger.error(f"Error during operation '{operation_name}': {e}", exc_info=True)
        if reraise:
            if isinstance(e, error_type):
                raise
            if issubclass(error_type, BaseError):
                # Use old BaseError signature for backward compatibility
                raise error_type(
                    f"{operation_name} failed",
                    original_exception=e,
                ) from e
            elif issubclass(error_type, NewBaseError):
                # Use new BaseError signature with enhanced features
                raise error_type(
                    f"{operation_name} failed",
                    context={"operation": operation_name},
                    original_exception=e,
                ) from e
            else:
                # For standard exceptions, create a simple message
                raise error_type(f"{operation_name} failed: {e}") from e


def error_handler(
    operation_name: str,
    error_type: Type[Exception],
    reraise: bool = True,
    logger: Optional[logging.Logger] = None,
) -> Callable[[Callable[..., _R]], Callable[..., Optional[_R]]]:
    """Decorator for consistent error handling in synchronous functions."""
    effective_logger = logger or module_logger

    def decorator(func: Callable[..., _R]) -> Callable[..., Optional[_R]]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Optional[_R]:
            effective_logger.info(
                f"Calling function '{func.__name__}' for operation: {operation_name}"
            )
            try:
                result = func(*args, **kwargs)
                effective_logger.info(
                    f"Function '{func.__name__}' for '{operation_name}' completed successfully."
                )
                return result
            except Exception as e:
                effective_logger.error(
                    f"Error in '{func.__name__}' during '{operation_name}': {e}",
                    exc_info=True,
                )
                if reraise:
                    if isinstance(e, error_type):
                        raise
                    if issubclass(error_type, BaseError):
                        # Use old BaseError signature for backward compatibility
                        raise error_type(
                            f"Operation '{operation_name}' failed",
                            original_exception=e,
                        ) from e
                    elif issubclass(error_type, NewBaseError):
                        # Use new BaseError signature with enhanced features
                        raise error_type(
                            f"Operation '{operation_name}' failed",
                            context={"function": func.__name__},
                            original_exception=e,
                        ) from e
                    else:
                        raise error_type(
                            f"Operation '{operation_name}' (function: {func.__name__}) failed: {e}"
                        ) from e
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
    """Processes a list of items synchronously, handling errors for each item."""
    effective_logger = logger or module_logger
    successful_results: List[_RT] = []
    errors: List[Tuple[_IT, Exception]] = []

    effective_logger.info(
        f"Starting batch operation: {operation_name} for {len(items)} items."
    )

    for index, item in enumerate(items):
        item_repr = str(item)
        effective_logger.debug(
            f"Processing item {index + 1}/{len(items)} ('{item_repr}') for '{operation_name}'."
        )
        try:
            result = operation(item)
            successful_results.append(result)
        except Exception as e:
            effective_logger.error(
                f"Error processing item '{item_repr}' in '{operation_name}': {e}",
                exc_info=True,
            )
            errors.append((item, e))
            if not continue_on_error:
                effective_logger.warning(
                    f"Batch operation '{operation_name}' stopped early due to error on item '{item_repr}'."
                )
                break

    effective_logger.info(
        f"Batch operation '{operation_name}' completed. "
        f"Successful: {len(successful_results)}, Failed: {len(errors)}."
    )
    return successful_results, errors
