import logging
from pathlib import Path
from typing import Optional, Union

# Import the Settings model from the types module
from .config_types import Settings

# Import the manager and error classes from the configuration module
from .configuration import ConfigurationError, ConfigurationManager

logger = logging.getLogger(__name__)


# --- Global Configuration Manager Instance ---
# Keep a single instance to manage configuration loading efficiently.
_config_manager_instance: Optional[ConfigurationManager] = None


def get_config_manager(
    config_file: Optional[Union[str, Path]] = None, force_reload: bool = False
) -> ConfigurationManager:
    """
    Get the global ConfigurationManager instance, initializing or reloading as needed.

    Args:
        config_file: Optional path to a specific config file. If provided during
                     initialization or reload, this file will be used. If provided
                     when an instance already exists and force_reload=False, a
                     warning is logged as the existing instance might use a
                     different config file.
        force_reload: If True, forces re-initialization and reloading of the
                      configuration manager from all sources (defaults, file, env).

    Returns:
        The singleton ConfigurationManager instance.
    """
    global _config_manager_instance

    # Determine if a reload is needed or if the specified config file differs
    needs_init_or_reload = _config_manager_instance is None or force_reload
    config_file_specified_without_reload = (
        config_file is not None
        and _config_manager_instance is not None
        and not force_reload
    )

    if needs_init_or_reload:
        logger.debug(
            f"Initializing or reloading ConfigurationManager (force_reload={force_reload})."
        )
        # Pass the specific config file path during initialization
        _config_manager_instance = ConfigurationManager(
            settings_cls=Settings,
            config_file_path=config_file,
        )
        try:
            # Load config immediately upon creation/reload
            _config_manager_instance.load_config(force_reload=force_reload)
        except ConfigurationError as e:
            logger.error(f"Initial configuration loading failed: {e}")

    elif config_file_specified_without_reload:
        current_config_path = getattr(
            _config_manager_instance, "_config_file_path", "N/A"
        )
        logger.warning(
            f"get_config_manager called with config_file='{config_file}' but "
            f"force_reload=False. Returning existing manager instance which might be "
            f"using config file '{current_config_path}' or defaults."
        )

    assert _config_manager_instance is not None
    return _config_manager_instance


def load_settings(
    config_file: Optional[Union[str, Path]] = None,
    force_reload: bool = False,
    debug: bool = False,  # Added for backward compatibility
) -> Settings:
    """
    Load settings using the singleton ConfigurationManager.

    This function retrieves the global ConfigurationManager instance (initializing
    or reloading it if necessary based on arguments) and then calls its
    get_settings() method to obtain the final Settings object.

    Args:
        config_file: Optional path to a specific configuration file to use.
        force_reload: If True, forces reloading the configuration from all sources
                      before returning the settings object.
        debug: If True, enables debug logging level (backward compatibility).

    Returns:
        A populated Settings object. Falls back to defaults if loading fails.

    Raises:
        ConfigurationError: If creating even a default Settings object fails.
    """
    manager = get_config_manager(config_file=config_file, force_reload=force_reload)

    # Handle debug parameter for backward compatibility by passing a runtime override
    overrides = {}
    if debug:
        overrides["log_level"] = "DEBUG"

    settings = manager.get_settings(overrides=overrides if overrides else None)

    return settings


# Example of accessing settings (preferred way):
# from pytest_analyzer.utils import settings
# current_settings = settings.load_settings()
# print(current_settings.pytest_timeout)

# Or if you need the manager itself:
# manager = settings.get_config_manager()
# current_settings = manager.get_settings()
