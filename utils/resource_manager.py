import signal
import resource
import time
import logging
from contextlib import contextmanager
from functools import wraps
from typing import Optional, Callable, TypeVar, Any

T = TypeVar('T')
logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when execution time exceeds the limit"""
    pass


class MemoryLimitError(Exception):
    """Raised when memory usage exceeds the limit"""
    pass


@contextmanager
def timeout_context(seconds: int):
    """Context manager for timing out operations"""
    def handler(signum, frame):
        raise TimeoutError(f"Operation exceeded time limit of {seconds} seconds")
    
    # Store original handler
    original_handler = signal.getsignal(signal.SIGALRM)
    
    # Set new handler and alarm
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    
    try:
        yield
    finally:
        # Reset alarm and restore original handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)


def with_timeout(seconds: int) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for adding timeout to functions"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            with timeout_context(seconds):
                return func(*args, **kwargs)
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
    
    def __init__(self, 
                 max_memory_mb: Optional[int] = None,
                 max_time_seconds: Optional[int] = None):
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
        logger.debug(f"Peak memory usage: {self.peak_memory / (1024*1024):.2f} MB")
        
    def check(self):
        """Check if resource limits have been exceeded"""
        # Check time limit
        if self.max_time_seconds and time.time() - self.start_time > self.max_time_seconds:
            raise TimeoutError(f"Operation exceeded time limit of {self.max_time_seconds} seconds")
            
        # Check memory limit
        if self.max_memory_bytes:
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            self.peak_memory = max(self.peak_memory, usage)
            if usage > self.max_memory_bytes:
                raise MemoryLimitError(f"Operation exceeded memory limit of {self.max_memory_bytes / (1024*1024):.2f} MB")