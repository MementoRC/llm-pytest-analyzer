import signal
import resource
import time
import logging
import asyncio
from collections import defaultdict
from contextlib import contextmanager, asynccontextmanager
from functools import wraps
from typing import (
    Optional,
    Callable,
    TypeVar,
    Any,
    Dict,
    List,
    AsyncIterator,
    Iterator,
    Awaitable,
)

T = TypeVar("T")
R = TypeVar("R")
logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when execution time exceeds the limit"""

    pass


class MemoryLimitError(Exception):
    """Raised when memory usage exceeds the limit"""

    pass


@contextmanager
def timeout_context(seconds: float) -> Iterator[None]:
    """Context manager for timing out operations"""

    def handler(signum, frame):
        raise TimeoutError(f"Operation exceeded time limit of {seconds} seconds")

    # Check for negative timeout
    if seconds < 0:
        raise ValueError("Timeout seconds must be non-negative")

    # Store original handler
    original_handler = signal.getsignal(signal.SIGALRM)

    # Set new handler and timer
    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)  # Use setitimer for float support

    try:
        yield
    finally:
        # Reset timer and restore original handler
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, original_handler)


def with_timeout(seconds: float) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for adding timeout to functions"""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            with timeout_context(seconds):
                return func(*args, **kwargs)

        return wrapper

    return decorator


async def async_timeout(seconds: float) -> AsyncIterator[None]:
    """Asynchronous timeout context manager using asyncio.timeout()"""
    try:
        yield
    except asyncio.TimeoutError as e:
        raise TimeoutError(
            f"Async operation exceeded time limit of {seconds} seconds"
        ) from e


def async_with_timeout(
    seconds: float,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for adding timeout to async functions"""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            try:
                # Use asyncio.wait_for instead of signal-based timeout
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Async operation exceeded time limit of {seconds} seconds"
                )

        return wrapper

    return decorator


def limit_memory(max_mb: Optional[int] = None) -> None:
    """Set memory limits for the current process"""
    if max_mb is not None:
        try:
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            # Convert MB to bytes
            max_bytes = max_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_bytes, hard))
            logger.debug(f"Memory limit set to {max_mb} MB")
        except (resource.error, ValueError) as e:
            logger.warning(f"Failed to set memory limit: {e}")


class ResourceMonitor:
    """Monitors resource usage during operations"""

    def __init__(
        self,
        max_memory_mb: Optional[int] = None,
        max_time_seconds: Optional[int] = None,
    ):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024 if max_memory_mb else None
        self.max_time_seconds = max_time_seconds
        self.start_time = None
        self.peak_memory = 0

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.error(f"Operation failed with {exc_type.__name__}: {exc_val}")

        elapsed = time.time() - self.start_time
        logger.debug(f"Operation completed in {elapsed:.2f} seconds")
        logger.debug(f"Peak memory usage: {self.peak_memory / (1024 * 1024):.2f} MB")

    def check(self):
        """Check if resource limits have been exceeded"""
        # Check time limit
        if (
            self.max_time_seconds
            and time.time() - self.start_time > self.max_time_seconds
        ):
            raise TimeoutError(
                f"Operation exceeded time limit of {self.max_time_seconds} seconds"
            )

        # Check memory limit
        if self.max_memory_bytes:
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            self.peak_memory = max(self.peak_memory, usage)
            if usage > self.max_memory_bytes:
                raise MemoryLimitError(
                    f"Operation exceeded memory limit of {self.max_memory_bytes / (1024 * 1024):.2f} MB"
                )


class AsyncResourceMonitor:
    """Asynchronous version of resource monitor using asyncio"""

    def __init__(
        self,
        max_memory_mb: Optional[int] = None,
        max_time_seconds: Optional[int] = None,
    ):
        self.max_memory_bytes = max_memory_mb * 1024 * 1024 if max_memory_mb else None
        self.max_time_seconds = max_time_seconds
        self.start_time = None
        self.peak_memory = 0

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.error(f"Async operation failed with {exc_type.__name__}: {exc_val}")

        elapsed = time.time() - self.start_time
        logger.debug(f"Async operation completed in {elapsed:.2f} seconds")
        logger.debug(f"Peak memory usage: {self.peak_memory / (1024 * 1024):.2f} MB")

    async def check(self):
        """Check if resource limits have been exceeded (async version)"""
        # Check time limit
        if (
            self.max_time_seconds
            and time.time() - self.start_time > self.max_time_seconds
        ):
            raise TimeoutError(
                f"Async operation exceeded time limit of {self.max_time_seconds} seconds"
            )

        # Check memory limit
        if self.max_memory_bytes:
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            self.peak_memory = max(self.peak_memory, usage)
            if usage > self.max_memory_bytes:
                raise MemoryLimitError(
                    f"Operation exceeded memory limit of {self.max_memory_bytes / (1024 * 1024):.2f} MB"
                )


class PerformanceTracker:
    """
    Tracks performance metrics for operations.

    This class provides a way to measure execution times,
    track success rates, and generate reports.
    """

    def __init__(self) -> None:
        self.timings: Dict[str, List[float]] = defaultdict(list)
        self.counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.start_times: Dict[str, float] = {}
        self._active_contexts: List[str] = []

    def start(self, operation: str) -> None:
        """Start timing an operation"""
        self.start_times[operation] = time.time()

    def stop(self, operation: str, success: bool = True) -> float:
        """Stop timing an operation and record its duration"""
        if operation not in self.start_times:
            logger.warning(f"Operation {operation} was not started")
            return 0.0

        duration = time.time() - self.start_times.pop(operation)
        self.timings[operation].append(duration)

        status = "success" if success else "failure"
        self.counts[operation][status] += 1

        return duration

    @contextmanager
    def track(self, operation: str) -> Iterator[None]:
        """Context manager for tracking operation performance"""
        parent_context = self._active_contexts[-1] if self._active_contexts else None
        context_name = f"{parent_context}.{operation}" if parent_context else operation
        self._active_contexts.append(context_name)

        self.start(context_name)
        success = True
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            self.stop(context_name, success)
            self._active_contexts.pop()

    @asynccontextmanager
    async def async_track(self, operation: str) -> AsyncIterator[None]:
        """Async context manager for tracking operation performance"""
        parent_context = self._active_contexts[-1] if self._active_contexts else None
        context_name = f"{parent_context}.{operation}" if parent_context else operation
        self._active_contexts.append(context_name)

        self.start(context_name)
        success = True
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            self.stop(context_name, success)
            self._active_contexts.pop()

    def get_metrics(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """Get performance metrics for specific operation or all operations"""
        if operation:
            return self._calculate_metrics_for_operation(operation)

        return {
            op: self._calculate_metrics_for_operation(op) for op in self.timings.keys()
        }

    def _calculate_metrics_for_operation(self, operation: str) -> Dict[str, Any]:
        """Calculate metrics for a specific operation"""
        timings = self.timings.get(operation, [])
        counts = self.counts.get(operation, {})

        if not timings:
            return {
                "calls": 0,
                "success_rate": 0.0,
                "avg_time": 0.0,
                "min_time": 0.0,
                "max_time": 0.0,
                "total_time": 0.0,
            }

        total_calls = sum(counts.values())
        success_calls = counts.get("success", 0)

        return {
            "calls": total_calls,
            "success_rate": (success_calls / total_calls) if total_calls > 0 else 0.0,
            "avg_time": sum(timings) / len(timings),
            "min_time": min(timings),
            "max_time": max(timings),
            "total_time": sum(timings),
        }

    def report(self) -> str:
        """Generate a performance report as a string"""
        metrics = self.get_metrics()

        lines = ["Performance Metrics:"]
        for operation, data in metrics.items():
            lines.append(f"  {operation}:")
            lines.append(f"    Calls: {data['calls']}")
            lines.append(f"    Success Rate: {data['success_rate']:.2%}")
            lines.append(f"    Avg Time: {data['avg_time']:.4f}s")
            lines.append(f"    Min Time: {data['min_time']:.4f}s")
            lines.append(f"    Max Time: {data['max_time']:.4f}s")
            lines.append(f"    Total Time: {data['total_time']:.4f}s")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all tracked metrics"""
        self.timings.clear()
        self.counts.clear()
        self.start_times.clear()
        self._active_contexts.clear()


# Create a global performance tracker instance
performance_tracker = PerformanceTracker()


async def batch_process(
    items: List[Any],
    process_func: Callable[[Any], Awaitable[R]],
    batch_size: int = 5,
    max_concurrency: int = 10,
) -> List[Optional[R]]:
    """
    Process a list of items in batches with controlled concurrency.

    Args:
        items: List of items to process
        process_func: Async function to process each item
        batch_size: Number of items to process in each batch
        max_concurrency: Maximum number of concurrent tasks

    Returns:
        List of results in the same order as the input items
    """
    results: List[Optional[R]] = []

    # Process items in batches
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        batch_tasks = []

        # Create tasks for batch processing with semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrency)

        async def process_with_semaphore(item):
            async with semaphore:
                return await process_func(item)

        # Start tasks
        for item in batch:
            task = asyncio.create_task(process_with_semaphore(item))
            batch_tasks.append(task)

        # Wait for batch completion and collect results
        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

        # Handle exceptions
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Error in batch processing: {result}")
                results.append(None)
            else:
                # result is expected to be of type R but may be Any; ignore strict type checks
                results.append(result)  # type: ignore[arg-type]

    return results
