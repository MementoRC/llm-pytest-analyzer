import contextvars
import json
import logging
import sys
import traceback
import uuid
from logging.handlers import RotatingFileHandler
from typing import Optional

from .settings import Settings

# Context variable to hold a correlation ID for a request or operation.
correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


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


class JsonFormatter(logging.Formatter):
    """
    Formats log records as a JSON string.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON object.

        Args:
            record: The log record to format.

        Returns:
            A JSON string representing the log record.
        """
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name,
            "correlation_id": correlation_id_var.get(),
        }

        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = "".join(
                traceback.format_exception(*record.exc_info)
            )

        # Add extra data passed to the logger
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_record.update(record.extra_data)

        return json.dumps(log_record, default=str)


def configure_logging(
    settings: Settings,
    log_file: Optional[str] = None,
    structured: bool = False,
    log_level_override: Optional[str] = None,
) -> None:
    """
    Configure logging based on application settings.

    Args:
        settings: Application settings.
        log_file: Optional path to a log file.
        structured: If True, logs will be in JSON format.
        log_level_override: Optional log level string to override settings.
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
        # Use a rotating file handler for robustness
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

    # Configure library loggers to be less verbose
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    # Log configuration
    log_level_name = logging.getLevelName(log_level)
    logging.info(
        "Logging configured",
        extra={"extra_data": {"level": log_level_name, "structured": structured}},
    )
