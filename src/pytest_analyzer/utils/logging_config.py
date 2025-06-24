import contextvars
import json
import logging
import logging.config
import sys
import time
import traceback
import uuid
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar

try:
    import structlog

    STRUCTLOG_AVAILABLE = True
except ImportError:
    structlog = None
    STRUCTLOG_AVAILABLE = False

from .settings import Settings

# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Any])

# Context variables for enhanced logging context
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)
user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_id", default=None
)
operation_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "operation", default=None
)
request_start_time_var: contextvars.ContextVar[Optional[float]] = (
    contextvars.ContextVar("request_start_time", default=None)
)

# Enhanced sensitive field patterns
SENSITIVE_PATTERNS = {
    "password",
    "secret",
    "token",
    "key",
    "auth",
    "api_key",
    "access_token",
    "refresh_token",
    "private_key",
    "cert",
    "certificate",
    "credentials",
    "session",
    "cookie",
    "authorization",
    "x-api-key",
    "bearer",
}


def set_correlation_id(cid: Optional[str] = None) -> str:
    """
    Sets a correlation ID for the current context.
    If no ID is provided, a new UUID is generated.

    Args:
        cid: The correlation ID to set.

    Returns:
        The correlation ID that was set.
    """
    if cid is None:
        cid = f"cid_{uuid.uuid4()}"
    correlation_id_var.set(cid)
    return cid


def set_logging_context(
    correlation_id: Optional[str] = None,
    user_id: Optional[str] = None,
    operation: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Sets multiple context variables for enhanced logging.

    Args:
        correlation_id: Correlation ID for request tracking
        user_id: User identifier for the current operation
        operation: Operation name for the current context

    Returns:
        Dictionary of context values that were set
    """
    context = {}

    if correlation_id is not None:
        correlation_id_var.set(correlation_id)
        context["correlation_id"] = correlation_id

    if user_id is not None:
        user_id_var.set(user_id)
        context["user_id"] = user_id

    if operation is not None:
        operation_var.set(operation)
        context["operation"] = operation
        # Set start time for performance tracking
        request_start_time_var.set(time.time())

    return context


def get_logging_context() -> Dict[str, Optional[str]]:
    """
    Gets the current logging context.

    Returns:
        Dictionary containing current context variables
    """
    return {
        "correlation_id": correlation_id_var.get(),
        "user_id": user_id_var.get(),
        "operation": operation_var.get(),
        "request_start_time": request_start_time_var.get(),
    }


def clear_logging_context() -> None:
    """Clears all logging context variables."""
    correlation_id_var.set(None)
    user_id_var.set(None)
    operation_var.set(None)
    request_start_time_var.set(None)


def mask_sensitive_data(data: Any, additional_patterns: Optional[set] = None) -> Any:
    """
    Recursively mask sensitive information in data structures.

    Args:
        data: Data to sanitize
        additional_patterns: Additional sensitive field patterns

    Returns:
        Sanitized data with sensitive fields masked
    """
    patterns = SENSITIVE_PATTERNS
    if additional_patterns:
        patterns = patterns.union(additional_patterns)

    def _mask_recursive(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: "***MASKED***"
                if any(pattern.lower() in k.lower() for pattern in patterns)
                else _mask_recursive(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [_mask_recursive(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(_mask_recursive(item) for item in obj)
        else:
            return obj

    return _mask_recursive(data)


class JsonFormatter(logging.Formatter):
    """
    Enhanced JSON formatter with context variables and sensitive data masking.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON object with enhanced context.

        Args:
            record: The log record to format.

        Returns:
            A JSON string representing the log record.
        """
        # Get performance metrics if available
        duration_ms = None
        start_time = request_start_time_var.get()
        if start_time is not None:
            duration_ms = (time.time() - start_time) * 1000

        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "correlation_id": correlation_id_var.get(),
            "user_id": user_id_var.get(),
            "operation": operation_var.get(),
        }

        # Add duration if available
        if duration_ms is not None:
            log_record["duration_ms"] = round(duration_ms, 2)

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = "".join(
                traceback.format_exception(*record.exc_info)
            )

        # Add extra data passed to the logger (with sensitive data masking)
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            masked_extra = mask_sensitive_data(record.extra_data)
            log_record.update(masked_extra)

        # Mask any sensitive data in the log record itself
        log_record = mask_sensitive_data(log_record)

        return json.dumps(log_record, default=str)


def log_performance(
    operation_name: Optional[str] = None,
    log_args: bool = False,
    min_duration_ms: float = 0.0,
) -> Callable[[F], F]:
    """
    Decorator to log function execution time and performance metrics.

    Args:
        operation_name: Name of the operation (defaults to function name)
        log_args: Whether to log function arguments (be careful with sensitive data)
        min_duration_ms: Minimum duration in ms to log (filters out fast operations)

    Returns:
        Decorated function with performance logging
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            # Set operation context
            original_operation = operation_var.get()
            operation_var.set(op_name)
            request_start_time_var.set(start_time)

            logger = logging.getLogger(func.__module__)

            try:
                if log_args:
                    # Mask sensitive data in arguments
                    safe_args = mask_sensitive_data({"args": args, "kwargs": kwargs})
                    logger.debug(f"Starting {op_name}", extra={"extra_data": safe_args})

                result = func(*args, **kwargs)

                duration_ms = (time.time() - start_time) * 1000
                if duration_ms >= min_duration_ms:
                    logger.info(
                        f"Completed {op_name}",
                        extra={
                            "extra_data": {
                                "operation": op_name,
                                "duration_ms": round(duration_ms, 2),
                                "success": True,
                            }
                        },
                    )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Failed {op_name}",
                    extra={
                        "extra_data": {
                            "operation": op_name,
                            "duration_ms": round(duration_ms, 2),
                            "success": False,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        }
                    },
                    exc_info=True,
                )
                raise
            finally:
                # Restore original operation context
                operation_var.set(original_operation)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            # Set operation context
            original_operation = operation_var.get()
            operation_var.set(op_name)
            request_start_time_var.set(start_time)

            logger = logging.getLogger(func.__module__)

            try:
                if log_args:
                    # Mask sensitive data in arguments
                    safe_args = mask_sensitive_data({"args": args, "kwargs": kwargs})
                    logger.debug(f"Starting {op_name}", extra={"extra_data": safe_args})

                result = await func(*args, **kwargs)

                duration_ms = (time.time() - start_time) * 1000
                if duration_ms >= min_duration_ms:
                    logger.info(
                        f"Completed {op_name}",
                        extra={
                            "extra_data": {
                                "operation": op_name,
                                "duration_ms": round(duration_ms, 2),
                                "success": True,
                            }
                        },
                    )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Failed {op_name}",
                    extra={
                        "extra_data": {
                            "operation": op_name,
                            "duration_ms": round(duration_ms, 2),
                            "success": False,
                            "error": str(e),
                            "error_type": type(e).__name__,
                        }
                    },
                    exc_info=True,
                )
                raise
            finally:
                # Restore original operation context
                operation_var.set(original_operation)

        # Return appropriate wrapper based on function type
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


def configure_logging(
    settings: Settings,
    log_file: Optional[str] = None,
    structured: bool = False,
    log_level_override: Optional[str] = None,
    use_structlog: bool = True,
    module_levels: Optional[Dict[str, str]] = None,
    log_rotation_config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Enhanced logging configuration with structlog support and module-specific levels.

    Args:
        settings: Application settings.
        log_file: Optional path to a log file.
        structured: If True, logs will be in JSON format.
        log_level_override: Optional log level string to override settings.
        use_structlog: Whether to use structlog for structured logging.
        module_levels: Dictionary of module names to log levels.
        log_rotation_config: Configuration for log rotation (maxBytes, backupCount, etc.).
    """
    # Determine log level
    log_level = logging.INFO
    level_str_from_settings = "INFO"

    if hasattr(settings, "log_level"):
        level_str_from_settings = (
            settings.log_level.upper()
            if isinstance(settings.log_level, str)
            else "INFO"
        )
    elif hasattr(settings, "debug") and settings.debug:
        level_str_from_settings = "DEBUG"

    final_level_str = (
        log_level_override.upper() if log_level_override else level_str_from_settings
    )

    log_level = getattr(logging, final_level_str, logging.INFO)

    # Configure structlog if available and requested
    if STRUCTLOG_AVAILABLE and use_structlog and structured:
        # Configure structlog processors
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="ISO"),
        ]

        if structured:
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())

        structlog.configure(
            processors=processors,
            wrapper_class=structlog.make_filtering_bound_logger(log_level),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    # Set up log rotation configuration
    rotation_config = log_rotation_config or {}
    max_bytes = rotation_config.get("maxBytes", 10 * 1024 * 1024)  # 10MB
    backup_count = rotation_config.get("backupCount", 5)

    # Create formatters
    if structured:
        console_formatter = JsonFormatter()
        file_formatter = JsonFormatter()
    else:
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - [%(levelname)s] - %(message)s"
        )
        # File formatter includes filename and line number for debugging
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - [%(levelname)s] - %(filename)s:%(lineno)d - %(message)s"
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicate logs
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # Add file handler if log file specified
    if log_file:
        # Ensure directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use a rotating file handler with enhanced configuration
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

    # Configure module-specific log levels
    if module_levels:
        for module_name, level_str in module_levels.items():
            module_logger = logging.getLogger(module_name)
            module_level = getattr(logging, level_str.upper(), logging.INFO)
            module_logger.setLevel(module_level)

    # Configure library loggers to be less verbose
    default_library_levels = {
        "urllib3": logging.WARNING,
        "httpx": logging.WARNING,
        "requests": logging.WARNING,
        "anthropic": logging.INFO,
        "openai": logging.INFO,
        "hvac": logging.INFO,
    }

    for lib_name, lib_level in default_library_levels.items():
        logging.getLogger(lib_name).setLevel(lib_level)

    # Log configuration
    log_level_name = logging.getLevelName(log_level)
    config_info = {
        "level": log_level_name,
        "structured": structured,
        "structlog_enabled": STRUCTLOG_AVAILABLE and use_structlog and structured,
        "file_logging": log_file is not None,
        "module_levels": module_levels or {},
    }

    logging.info(
        "Enhanced logging configured",
        extra={"extra_data": config_info},
    )
