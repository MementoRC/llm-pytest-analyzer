import logging
import sys
from typing import Optional

from .settings import Settings


def configure_logging(settings: Settings, log_file: Optional[str] = None) -> None:
    """
    Configure logging based on application settings.

    Args:
        settings: Application settings
        log_file: Optional path to a log file
    """
    # Determine log level from settings
    # For backward compatibility, handle both log_level and debug attributes
    log_level = logging.INFO

    # Handle legacy `debug` attribute if it exists
    if hasattr(settings, "debug") and settings.debug:
        log_level = logging.DEBUG
    # Check for log_level in the new format
    elif hasattr(settings, "log_level"):
        level_str = (
            settings.log_level.upper()
            if isinstance(settings.log_level, str)
            else settings.log_level
        )
        if level_str == "DEBUG":
            log_level = logging.DEBUG
        elif level_str == "INFO":
            log_level = logging.INFO
        elif level_str == "WARNING":
            log_level = logging.WARNING
        elif level_str == "ERROR":
            log_level = logging.ERROR
        elif level_str == "CRITICAL":
            log_level = logging.CRITICAL

    # Create formatters
    console_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)

    # Add file handler if log file specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)

    # Configure library loggers to be less verbose
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    # Log configuration
    log_level_name = logging.getLevelName(log_level)
    logging.info(f"Logging configured with level {log_level_name}")
