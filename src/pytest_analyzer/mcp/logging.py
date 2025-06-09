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

from ..utils.logging_config import configure_logging

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
        """Sanitize sensitive information from messages."""
        sensitive_fields = ["password", "token", "secret", "key", "auth"]

        def _sanitize_recursive(data: Any) -> Any:
            if isinstance(data, dict):
                sanitized_data = {}
                for k, v in data.items():
                    if k in sensitive_fields:
                        sanitized_data[k] = "***"
                    else:
                        sanitized_data[k] = _sanitize_recursive(v)
                return sanitized_data
            elif isinstance(data, list):
                return [_sanitize_recursive(item) for item in data]
            else:
                return data

        sanitized_message_obj = _sanitize_recursive(message)
        return json.dumps(sanitized_message_obj)

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
        """Log security-related events."""
        sanitized_details = {
            k: "***" if k in ["token", "password"] else v for k, v in details.items()
        }

        self.logger.log(
            level,
            f"Security event: {event_type}",
            extra={
                "security_event": event_type,
                "details": sanitized_details,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def get_metrics(self) -> Dict[str, MCPMetrics]:
        """Get collected metrics."""
        return self.metrics.copy()


def log_tool_execution(logger: Optional[MCPLogger] = None) -> Callable[[F], F]:
    """Decorator to log tool execution with metrics."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            error = None
            success = False

            try:
                result = await func(*args, **kwargs)
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

        return wrapper  # type: ignore

    return decorator


# Global MCP logger instance
mcp_logger = MCPLogger()
