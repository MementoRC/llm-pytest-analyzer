"""
Main application module for the Pytest Analyzer GUI.

This module contains the QApplication instance and initialization logic
for the Pytest Analyzer GUI.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from ..utils.settings import Settings

# Add memory monitoring
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from memory_monitor import MemoryMonitor

# Configure logging
logger = logging.getLogger(__name__)


class SettingsCache:
    """Cache for QSettings to reduce I/O operations."""

    def __init__(self, settings: QSettings, ttl_seconds: int = 300):
        self.settings = settings
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple[Any, float]] = {}  # key -> (value, timestamp)

    def value(self, key: str, default_value: Any = None, value_type: Any = None) -> Any:
        """Get value from cache or QSettings."""
        now = time.time()

        # Check cache first
        if key in self._cache:
            cached_value, timestamp = self._cache[key]
            if now - timestamp < self.ttl_seconds:
                return cached_value

        # Load from QSettings and cache it
        if value_type is not None:
            value = self.settings.value(key, default_value, type=value_type)
        else:
            value = self.settings.value(key, default_value)
        self._cache[key] = (value, now)
        return value

    def setValue(self, key: str, value: Any) -> None:
        """Set value in QSettings and update cache."""
        self.settings.setValue(key, value)
        self._cache[key] = (value, time.time())

    def contains(self, key: str) -> bool:
        """Check if key exists (cached check)."""
        now = time.time()

        # Check cache first
        if key in self._cache:
            _, timestamp = self._cache[key]
            if now - timestamp < self.ttl_seconds:
                return True

        # Check QSettings and cache result
        exists = self.settings.contains(key)
        if exists:
            # Cache that it exists (we don't cache the value yet)
            self._cache[key] = (None, now)
        return exists

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    def sync(self) -> None:
        """Sync QSettings."""
        self.settings.sync()


class PytestAnalyzerApp(QApplication):
    """
    Main application class for the Pytest Analyzer GUI.

    This class initializes the QApplication and provides global
    application resources and settings.
    """

    def __init__(self, argv: List[str]):
        """
        Initialize the application.

        Args:
            argv: Command line arguments
        """
        super().__init__(argv)

        # Set application information
        self.setApplicationName("Pytest Analyzer")
        self.setApplicationVersion("0.1.0")  # Should match the package version
        self.setOrganizationName("MementoRC")
        self.setOrganizationDomain("github.com/MementoRC/llm-pytest-analyzer")

        # Default to fusion style for consistent cross-platform look
        self.setStyle("Fusion")

        # Initialize settings
        self._init_settings()

        # Load application resources
        self._init_resources()

        logger.info("PytestAnalyzerApp initialized")

    def _init_settings(self) -> None:
        """Initialize application settings."""
        # Create QSettings for GUI-specific settings with caching
        self._qsettings = QSettings()
        self.settings = SettingsCache(self._qsettings, ttl_seconds=300)  # 5 minute cache

        # Load core settings
        self.core_settings = Settings()

        # Try to load settings from last session
        if self.settings.contains("core_settings/project_root"):
            project_root = self.settings.value("core_settings/project_root", "")
            if project_root and Path(project_root).exists():
                self.core_settings.project_root = Path(project_root)

        # Load LLM settings
        self.core_settings.llm_provider = self.settings.value(
            "core_settings/llm_provider", self.core_settings.llm_provider
        )
        self.core_settings.llm_api_key_openai = self.settings.value(
            "core_settings/llm_api_key_openai", self.core_settings.llm_api_key_openai
        )
        self.core_settings.llm_api_key_anthropic = self.settings.value(
            "core_settings/llm_api_key_anthropic", self.core_settings.llm_api_key_anthropic
        )
        self.core_settings.llm_model_openai = self.settings.value(
            "core_settings/llm_model_openai", self.core_settings.llm_model_openai
        )
        self.core_settings.llm_model_anthropic = self.settings.value(
            "core_settings/llm_model_anthropic", self.core_settings.llm_model_anthropic
        )
        self.core_settings.llm_cache_enabled = self.settings.value(
            "core_settings/llm_cache_enabled", self.core_settings.llm_cache_enabled, value_type=bool
        )
        self.core_settings.llm_cache_ttl_seconds = self.settings.value(
            "core_settings/llm_cache_ttl_seconds",
            self.core_settings.llm_cache_ttl_seconds,
            value_type=int,
        )

        # Test Execution Settings
        self.core_settings.pytest_timeout = self.settings.value(
            "core_settings/pytest_timeout", self.core_settings.pytest_timeout, value_type=int
        )
        pytest_args_str = self.settings.value("core_settings/pytest_args", "")
        if pytest_args_str:  # Check if the setting exists and is not empty
            self.core_settings.pytest_args = pytest_args_str.split()
        # else: pytest_args is already default from Settings()

        self.core_settings.max_memory_mb = self.settings.value(
            "core_settings/max_memory_mb", self.core_settings.max_memory_mb, value_type=int
        )
        self.core_settings.parser_timeout = self.settings.value(
            "core_settings/parser_timeout", self.core_settings.parser_timeout, value_type=int
        )
        self.core_settings.analyzer_timeout = self.settings.value(
            "core_settings/analyzer_timeout", self.core_settings.analyzer_timeout, value_type=int
        )
        self.core_settings.batch_size = self.settings.value(
            "core_settings/batch_size", self.core_settings.batch_size, value_type=int
        )
        self.core_settings.max_concurrency = self.settings.value(
            "core_settings/max_concurrency", self.core_settings.max_concurrency, value_type=int
        )

        # Analysis Settings
        self.core_settings.max_failures = self.settings.value(
            "core_settings/max_failures", self.core_settings.max_failures, value_type=int
        )
        self.core_settings.max_suggestions = self.settings.value(
            "core_settings/max_suggestions", self.core_settings.max_suggestions, value_type=int
        )
        self.core_settings.max_suggestions_per_failure = self.settings.value(
            "core_settings/max_suggestions_per_failure",
            self.core_settings.max_suggestions_per_failure,
            value_type=int,
        )
        self.core_settings.min_confidence = self.settings.value(
            "core_settings/min_confidence", self.core_settings.min_confidence, value_type=float
        )
        self.core_settings.auto_apply = self.settings.value(
            "core_settings/auto_apply", self.core_settings.auto_apply, value_type=bool
        )

        # GUI Preferences (Core part)
        self.core_settings.preferred_format = self.settings.value(
            "core_settings/preferred_format", self.core_settings.preferred_format
        )
        self.core_settings.log_level = self.settings.value(
            "core_settings/log_level", self.core_settings.log_level
        )

        # Git Integration Settings
        self.core_settings.check_git = self.settings.value(
            "core_settings/check_git", self.core_settings.check_git, value_type=bool
        )
        self.core_settings.auto_init_git = self.settings.value(
            "core_settings/auto_init_git", self.core_settings.auto_init_git, value_type=bool
        )
        self.core_settings.use_git_branches = self.settings.value(
            "core_settings/use_git_branches", self.core_settings.use_git_branches, value_type=bool
        )

    def _init_resources(self) -> None:
        """Initialize application resources like icons and themes."""
        # TODO: Add proper resource loading when resources are added
        # self.setWindowIcon(QIcon(":/icons/app_icon.png"))
        pass

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a GUI setting by key.

        Args:
            key: The setting key
            default: Default value if setting doesn't exist

        Returns:
            The setting value
        """
        return self.settings.value(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """
        Set a GUI setting.

        Args:
            key: The setting key
            value: The setting value
        """
        self.settings.setValue(key, value)
        self.settings.sync()

    def save_core_llm_settings(self) -> None:
        """Save LLM-related core settings to QSettings."""
        self.settings.setValue("core_settings/llm_provider", self.core_settings.llm_provider)
        self.settings.setValue(
            "core_settings/llm_api_key_openai", self.core_settings.llm_api_key_openai
        )
        self.settings.setValue(
            "core_settings/llm_api_key_anthropic", self.core_settings.llm_api_key_anthropic
        )
        self.settings.setValue(
            "core_settings/llm_model_openai", self.core_settings.llm_model_openai
        )
        self.settings.setValue(
            "core_settings/llm_model_anthropic", self.core_settings.llm_model_anthropic
        )
        self.settings.setValue(
            "core_settings/llm_cache_enabled", self.core_settings.llm_cache_enabled
        )
        self.settings.setValue(
            "core_settings/llm_cache_ttl_seconds", self.core_settings.llm_cache_ttl_seconds
        )
        self.settings.sync()
        logger.info("LLM core settings saved to QSettings.")

    def save_all_core_settings_to_qsettings(self) -> None:
        """Saves all relevant core_settings to QSettings."""
        logger.info("Saving all configurable core settings to QSettings.")

        # LLM settings (uses existing method)
        self.save_core_llm_settings()

        # Test Execution Settings
        self.settings.setValue("core_settings/pytest_timeout", self.core_settings.pytest_timeout)
        self.settings.setValue(
            "core_settings/pytest_args", " ".join(self.core_settings.pytest_args)
        )
        self.settings.setValue("core_settings/max_memory_mb", self.core_settings.max_memory_mb)
        self.settings.setValue("core_settings/parser_timeout", self.core_settings.parser_timeout)
        self.settings.setValue(
            "core_settings/analyzer_timeout", self.core_settings.analyzer_timeout
        )
        self.settings.setValue("core_settings/batch_size", self.core_settings.batch_size)
        self.settings.setValue("core_settings/max_concurrency", self.core_settings.max_concurrency)

        # Analysis Settings
        self.settings.setValue("core_settings/max_failures", self.core_settings.max_failures)
        self.settings.setValue("core_settings/max_suggestions", self.core_settings.max_suggestions)
        self.settings.setValue(
            "core_settings/max_suggestions_per_failure",
            self.core_settings.max_suggestions_per_failure,
        )
        self.settings.setValue("core_settings/min_confidence", self.core_settings.min_confidence)
        self.settings.setValue("core_settings/auto_apply", self.core_settings.auto_apply)

        # GUI Preferences (Core part)
        self.settings.setValue(
            "core_settings/preferred_format", self.core_settings.preferred_format
        )
        self.settings.setValue("core_settings/log_level", self.core_settings.log_level)

        # Git Integration Settings
        self.settings.setValue("core_settings/check_git", self.core_settings.check_git)
        self.settings.setValue("core_settings/auto_init_git", self.core_settings.auto_init_git)
        self.settings.setValue(
            "core_settings/use_git_branches", self.core_settings.use_git_branches
        )

        self.settings.sync()
        logger.info("All configurable core settings saved to QSettings.")


def create_app(argv: Optional[List[str]] = None) -> PytestAnalyzerApp:
    """
    Create and initialize the application.

    Args:
        argv: Command line arguments (defaults to sys.argv)

    Returns:
        The initialized application instance
    """
    if argv is None:
        argv = sys.argv

    # In Qt6/PyQt6, high DPI scaling is enabled by default
    # No need to use the deprecated Qt5 attributes
    # For fine-tuning, we can set the high DPI scale factor rounding policy if needed
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Set memory management for GUI process
    try:
        import logging
        import resource

        logger = logging.getLogger(__name__)

        # Get current memory usage
        current_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024  # Convert to bytes
        logger.info(f"GUI process current memory usage: {current_mem / 1024 / 1024:.1f} MB")

        # Set a reasonable memory limit for the GUI process (768MB)
        # This prevents runaway memory consumption while allowing normal operation
        memory_limit = 768 * 1024 * 1024  # 768MB in bytes
        try:
            # Temporarily disable memory limit to allow GUI startup
            # resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            logger.info(
                f"Memory limit disabled temporarily for GUI startup: {memory_limit / 1024 / 1024:.1f} MB"
            )
        except OSError as e:
            logger.warning(f"Could not set memory limit: {e}")
    except Exception as e:
        logging.getLogger(__name__).warning(f"Memory management setup failed: {e}")

    # Create the application
    app = PytestAnalyzerApp(argv)

    # Start memory monitoring
    monitor = MemoryMonitor(interval=2.0)
    monitor.log_memory_state("APP_STARTUP")
    monitor.start_monitoring()

    # Store monitor in app for access
    app.memory_monitor = monitor

    return app
