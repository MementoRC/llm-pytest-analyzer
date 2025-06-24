"""MCP-specific logging implementation.

Provides specialized logging functionality for MCP protocol messages,
tool execution metrics, and security events while integrating with
the existing logging infrastructure.
"""

import functools
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional, TypeVar

from ..utils.logging_config import (
    configure_logging,
    log_performance,
    mask_sensitive_data,
    set_logging_context,
)

# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class MCPMetrics:
    """Metrics for MCP operations."""

    operation: str
    start_time: float
    end_time: float
    duration_ms: float
    success: bool
    error: Optional[str] = None


class MCPLogger:
    """Specialized logger for MCP operations with metrics and security logging."""

    def __init__(self, name: str = "mcp", settings: Optional[Any] = None):
        """Initialize MCP logger.

        Args:
            name: Logger name
            settings: Optional settings instance for configuration
        """
        self.logger = logging.getLogger(name)
        self.metrics: Dict[str, MCPMetrics] = {}

        # Configure logging if settings provided
        if settings:
            configure_logging(settings)

    def sanitize_message(self, message: Any) -> str:
        """Sanitize sensitive information from messages using enhanced masking."""
        # Use the enhanced mask_sensitive_data function
        sanitized_message_obj = mask_sensitive_data(message)
        return json.dumps(sanitized_message_obj, default=str)

    def log_protocol_message(
        self, direction: str, message: Any, level: int = logging.DEBUG
    ) -> None:
        """Log MCP protocol message with sanitization."""
        sanitized = self.sanitize_message(message)
        self.logger.log(
            level,
            f"MCP {direction}: {sanitized}",
            extra={
                "mcp_direction": direction,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def log_tool_execution(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Log tool execution with metrics."""
        metrics = MCPMetrics(
            operation=f"tool_{tool_name}",
            start_time=time.time() - (duration_ms / 1000),
            end_time=time.time(),
            duration_ms=duration_ms,
            success=success,
            error=error,
        )

        self.metrics[tool_name] = metrics

        log_level = logging.INFO if success else logging.ERROR
        self.logger.log(
            log_level,
            f"Tool execution: {tool_name} ({'success' if success else 'failed'}) "
            f"duration={duration_ms:.2f}ms{f' error={error}' if error else ''}",
            extra={"metrics": asdict(metrics)},
        )

    def log_security_event(
        self, event_type: str, details: Dict[str, Any], level: int = logging.INFO
    ) -> None:
        """Log security-related events with enhanced sanitization."""
        # Use enhanced masking for all security event details
        sanitized_details = mask_sensitive_data(details)

        self.logger.log(
            level,
            f"Security event: {event_type}",
            extra={
                "extra_data": {
                    "security_event": event_type,
                    "event_details": sanitized_details,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            },
        )

    def get_metrics(self) -> Dict[str, MCPMetrics]:
        """Get collected metrics."""
        return self.metrics.copy()

    def set_mcp_context(
        self,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> None:
        """Set MCP-specific logging context."""
        set_logging_context(
            correlation_id=correlation_id,
            user_id=user_id,
            operation=operation,
        )

        self.logger.debug(
            "MCP context set",
            extra={
                "extra_data": {
                    "correlation_id": correlation_id,
                    "user_id": user_id,
                    "operation": operation,
                }
            },
        )

    def log_request_response(
        self,
        request_data: Any,
        response_data: Any,
        duration_ms: Optional[float] = None,
        level: int = logging.DEBUG,
    ) -> None:
        """Log MCP request/response pairs with sanitization."""
        sanitized_request = mask_sensitive_data(request_data)
        sanitized_response = mask_sensitive_data(response_data)

        log_data = {
            "request": sanitized_request,
            "response": sanitized_response,
        }

        if duration_ms is not None:
            log_data["duration_ms"] = round(duration_ms, 2)

        self.logger.log(
            level,
            "MCP request/response",
            extra={"extra_data": log_data},
        )


def log_tool_execution(logger: Optional[MCPLogger] = None) -> Callable[[F], F]:
    """Decorator to log tool execution with enhanced metrics and performance tracking."""

    def decorator(func: F) -> F:
        # Apply the enhanced performance logging decorator
        perf_decorated = log_performance(
            operation_name=f"mcp_tool_{func.__name__}",
            log_args=False,  # Don't log args for MCP tools (may contain sensitive data)
            min_duration_ms=1.0,  # Log operations taking more than 1ms
        )(func)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            error = None
            success = False

            try:
                result = await perf_decorated(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                if logger:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.log_tool_execution(
                        tool_name=func.__name__,
                        duration_ms=duration_ms,
                        success=success,
                        error=error,
                    )

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            error = None
            success = False

            try:
                result = perf_decorated(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                error = str(e)
                raise
            finally:
                if logger:
                    duration_ms = (time.time() - start_time) * 1000
                    logger.log_tool_execution(
                        tool_name=func.__name__,
                        duration_ms=duration_ms,
                        success=success,
                        error=error,
                    )

        # Return appropriate wrapper based on function type
        if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# Global MCP logger instance
mcp_logger = MCPLogger()
