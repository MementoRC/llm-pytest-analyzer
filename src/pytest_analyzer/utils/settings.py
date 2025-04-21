import logging
from pathlib import Path
from typing import Optional, Union  # Added List and Dict

# Import the manager and error classes from the configuration module
from .configuration import ConfigurationManager, ConfigurationError

# Import the Settings dataclass definition from the types module
from .config_types import Settings

# No longer need TYPE_CHECKING block for Settings

logger = logging.getLogger(__name__)


# --- Global Configuration Manager Instance ---
# Keep a single instance to manage configuration loading efficiently.
_config_manager_instance: Optional[ConfigurationManager] = None


def get_config_manager(
    config_file: Optional[Union[str, Path]] = None, force_reload: bool = False
) -> ConfigurationManager:
    """
    Get the global ConfigurationManager instance, initializing if needed.

    Args:
        config_file: Optional path to a specific config file to use during initialization.
        force_reload: If True, forces reloading the configuration.

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
            settings_cls=Settings,  # Settings is now imported from .config_types
            config_file_path=config_file,
            # env_prefix can be customized here if needed
        )
        try:
            # Load config immediately upon creation/reload
            _config_manager_instance.load_config(force_reload=force_reload)
        except ConfigurationError as e:
            # Log the error; the manager might still be usable with defaults
            # if get_settings() handles this gracefully (which it should).
            logger.error(f"Initial configuration loading failed: {e}")
            # Do not re-raise here; let get_settings handle fallback if possible.

    elif config_file_specified_without_reload:
        # Warn if called with a specific file but not reloading the existing instance
        current_config_path = getattr(
            _config_manager_instance, "_config_file_path", "N/A"
        )
        logger.warning(
            f"get_config_manager called with config_file='{config_file}' but "
            f"force_reload=False. Returning existing manager instance which might be "
            f"using config file '{current_config_path}' or defaults."
        )

    # Always return the current instance
    assert _config_manager_instance is not None
    return _config_manager_instance


def load_settings(
    config_file: Optional[Union[str, Path]] = None, force_reload: bool = False
) -> Settings:
    """
    Load settings using the ConfigurationManager.

    This function initializes and uses the ConfigurationManager to load settings
    from defaults, config file (if found), and environment variables.

    Args:
        config_file: Optional path to a specific configuration file.
        force_reload: If True, forces reloading the configuration from all sources.

    Load settings using the singleton ConfigurationManager.

    This function retrieves the global ConfigurationManager instance (initializing
    or reloading it if necessary based on arguments) and then calls its
    get_settings() method to obtain the final Settings object.

    Args:
        config_file: Optional path to a specific configuration file to use.
        force_reload: If True, forces reloading the configuration from all sources
                      before returning the settings object.

    Returns:
        A populated Settings object. Falls back to defaults if loading fails
        and default instantiation is possible.

    Raises:
        ConfigurationError: If creating even a default Settings object fails.
    """
    manager = get_config_manager(config_file=config_file, force_reload=force_reload)
    # get_settings now handles potential loading errors and fallbacks internally
    return manager.get_settings()


# Example of accessing settings (preferred way):
# from pytest_analyzer.utils import settings
# current_settings = settings.load_settings()
# print(current_settings.pytest_timeout)

# Or if you need the manager itself:
# manager = settings.get_config_manager()
# current_settings = manager.get_settings()
