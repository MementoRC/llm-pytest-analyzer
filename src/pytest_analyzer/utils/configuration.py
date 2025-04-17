import os
import yaml
import logging
from pathlib import Path
from typing import Optional, Type, TypeVar, Any, Dict, List, Union
from dataclasses import fields, is_dataclass, MISSING

# Import Settings from the config_types module to avoid circular dependency
from .config_types import Settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


# --- Configuration Manager ---

# Define a specific exception for configuration errors
class ConfigurationError(Exception):
    """Custom exception for configuration loading errors."""
    pass


class ConfigurationManager:
    """
    Manages loading configuration settings from multiple sources.

    Handles hierarchical loading:
    1. Default values from the Settings dataclass.
    2. Values from a YAML configuration file.
    3. Values from environment variables.
    """
    DEFAULT_CONFIG_FILES = ["pytest-analyzer.yaml", "pytest-analyzer.yml"]
    ENV_PREFIX = "PYTEST_ANALYZER_"

    def __init__(
        self,
        settings_cls: Type[T] = Settings,
        config_file_path: Optional[Union[str, Path]] = None,
        env_prefix: str = ENV_PREFIX
    ):
        """
        Initialize the ConfigurationManager.

        Args:
            settings_cls: The dataclass type to use for settings structure and defaults.
            config_file_path: Optional path to a specific configuration file.
                               If None, searches for default files in CWD and project root.
            env_prefix: Prefix for environment variables (e.g., "PYTEST_ANALYZER_").
        """
        if not is_dataclass(settings_cls):
            raise TypeError(f"{settings_cls.__name__} must be a dataclass.")

        self.settings_cls: Type[T] = settings_cls
        self.env_prefix: str = env_prefix
        self._config_file_path: Optional[Path] = self._resolve_config_file_path(config_file_path)
        self._config: Dict[str, Any] = {}
        self._loaded: bool = False
        # Use Type[T] for the cache instance type hint, matching settings_cls
        self._settings_instance: Optional[T] = None # Cache the created instance

    def _resolve_config_file_path(self, specific_path: Optional[Union[str, Path]]) -> Optional[Path]:
        """
        Find the configuration file path.
        Searches in CWD and optionally the parent directories up to the root.
        Does NOT rely on Settings.project_root default during search.
        """
        search_paths: List[Path] = []

        if specific_path:
            p = Path(specific_path)
            if p.is_file():
                logger.debug(f"Using specified configuration file: {p}")
                return p
            else:
                logger.warning(f"Specified configuration file not found: {specific_path}")
                # Continue searching default locations even if specific path fails
                # Or raise ConfigurationError here if specific path must exist?
                # Let's allow fallback to defaults for now.

        # Search in current working directory
        cwd = Path.cwd()
        search_paths.extend(cwd / name for name in self.DEFAULT_CONFIG_FILES)

        # Search in parent directories up to the root (or home dir as a practical limit)
        # This helps find config files in parent project directories
        current = cwd.parent
        home = Path.home()
        while current != current.parent and current != home:
             search_paths.extend(current / name for name in self.DEFAULT_CONFIG_FILES)
             current = current.parent
        # Check home directory itself if not already checked
        if home != cwd and home != cwd.parent:
             search_paths.extend(home / name for name in self.DEFAULT_CONFIG_FILES)


        for path in search_paths:
            # Use resolve() to handle potential symlinks and get absolute path
            try:
                resolved_path = path.resolve()
                if resolved_path.is_file():
                    logger.debug(f"Found configuration file: {resolved_path}")
                    return resolved_path
            except OSError as e: # Handle potential permission errors etc. during resolve/is_file
                logger.debug(f"Could not access potential config file {path}: {e}")


        logger.debug("No configuration file found in standard locations.")
        return None

    def load_config(self, force_reload: bool = False) -> None:
        """Load configuration from all sources."""
        if self._loaded and not force_reload:
            return

        # Reset state for reload
        self._config = {}
        self._settings_instance = None

        try:
            self._config = self._load_defaults()
            self._config.update(self._load_from_file())
            self._config.update(self._load_from_env())
            self._loaded = True
            logger.debug("Configuration loaded successfully.")
        except Exception as e:
            self._loaded = False # Ensure loaded is false on error
            logger.error(f"Failed to load configuration: {e}")
            # Propagate the error to the caller
            raise ConfigurationError("Configuration loading failed") from e

    def _load_defaults(self) -> Dict[str, Any]:
        """Load default values from the Settings dataclass."""
        defaults = {}
        try:
            # Instantiate to get defaults, handling potential __post_init__ errors
            # We need an instance to correctly handle default_factory
            default_instance = self.settings_cls()
            for f in fields(self.settings_cls):
                # Use getattr to respect potential default_factory logic and __post_init__
                try:
                    defaults[f.name] = getattr(default_instance, f.name)
                except AttributeError:
                    # Handle cases where __post_init__ might remove an attribute or fail
                    if f.default is not MISSING:
                        defaults[f.name] = f.default
                    elif f.default_factory is not MISSING:
                        defaults[f.name] = f.default_factory()
                    else:
                        # This case implies a required field with no default,
                        # which should ideally be caught by dataclass itself,
                        # but we log a warning just in case.
                        logger.warning(f"Could not determine default value for required field '{f.name}'")

            logger.debug("Loaded defaults from Settings dataclass.")
        except Exception as e:
            logger.error(f"Critical error initializing defaults for {self.settings_cls.__name__}: {e}")
            # This is more critical, perhaps re-raise or return empty dict?
            # Returning empty allows fallback but might hide issues. Let's raise.
            raise ConfigurationError(f"Could not initialize default settings: {e}") from e
        return defaults


    def _load_from_file(self) -> Dict[str, Any]:
        """Load configuration from the YAML file."""
        if not self._config_file_path:
            return {}

        try:
            with open(self._config_file_path, 'r') as f:
                file_config = yaml.safe_load(f)
                if file_config and isinstance(file_config, dict):
                    logger.info(f"Loaded configuration from file: {self._config_file_path}")
                    # Filter only keys relevant to Settings
                    valid_keys = {f.name for f in fields(self.settings_cls)}
                    filtered_config = {k: v for k, v in file_config.items() if k in valid_keys}
                    return filtered_config
                elif file_config is not None:
                     logger.warning(f"Configuration file {self._config_file_path} does not contain a dictionary.")
                     return {}
                else:
                    # File is empty
                    return {}
        except FileNotFoundError:
            # This case should ideally be handled by _resolve_config_file_path, but check again.
            logger.debug(f"Configuration file not found: {self._config_file_path}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration file {self._config_file_path}: {e}")
            raise ConfigurationError(f"Invalid YAML format in {self._config_file_path}") from e
        except Exception as e:
            logger.error(f"Error reading configuration file {self._config_file_path}: {e}")
            raise ConfigurationError(f"Could not read configuration file {self._config_file_path}") from e

    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        env_config = {}
        valid_fields = {f.name: f for f in fields(self.settings_cls)}

        for env_var, value in os.environ.items():
            if env_var.startswith(self.env_prefix):
                # Convert PYTEST_ANALYZER_SETTING_NAME to setting_name
                setting_name = env_var[len(self.env_prefix):].lower()

                if setting_name in valid_fields:
                    field_info = valid_fields[setting_name]
                    try:
                        typed_value = self._convert_type(value, field_info.type)
                        env_config[setting_name] = typed_value
                        logger.debug(f"Loaded '{setting_name}' from environment variable '{env_var}'.")
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"Could not convert environment variable {env_var} "
                            f"value '{value}' to type {field_info.type}: {e}"
                        )
                # else:
                    # Optional: Log ignored env vars
                    # logger.debug(f"Ignoring environment variable '{env_var}' as it doesn't match a setting.")

        return env_config

    def _convert_type(self, value: str, target_type: Type) -> Any:
        """Convert string value to the target type."""
        origin_type = getattr(target_type, '__origin__', None)
        args = getattr(target_type, '__args__', [])

        if target_type is bool:
            # Handle boolean conversion robustly
            return value.lower() in ('true', '1', 'yes', 'y', 'on')
        elif target_type is int:
            return int(value)
        elif target_type is float:
            return float(value)
        elif target_type is Path:
            return Path(value)
        elif target_type is str:
            return value
        elif origin_type is Union and type(None) in args:
             # Handle Optional[T] - try converting to the non-None type
             non_none_type = next(t for t in args if t is not type(None))
             return self._convert_type(value, non_none_type)
        elif origin_type is list or target_type is List:
            # Basic list support: comma-separated strings
            # Assumes list of strings if no specific type arg, otherwise tries to convert elements
            element_type = args[0] if args else str
            return [self._convert_type(item.strip(), element_type) for item in value.split(',') if item.strip()]
        elif origin_type is dict or target_type is Dict:
             # Basic dict support: expects 'key1=value1,key2=value2'
             # Assumes Dict[str, str] if no specific type args
             key_type = args[0] if args else str
             value_type = args[1] if len(args) > 1 else str
             result_dict = {}
             for item in value.split(','):
                 if '=' in item:
                     k, v = item.split('=', 1)
                     result_dict[self._convert_type(k.strip(), key_type)] = self._convert_type(v.strip(), value_type)
             return result_dict

        # Fallback or raise error for unsupported types
        try:
            # Attempt direct conversion for simple types not explicitly handled
            return target_type(value)
        except (ValueError, TypeError):
             raise TypeError(f"Unsupported type conversion for {target_type} from environment variable string.")


    def get_settings(self) -> T:
        """
        Return the final configuration merged from all sources as a Settings object.

        Returns:
            An instance of the settings_cls populated with the merged configuration.

        Raises:
            ConfigurationError: If configuration hasn't been loaded or fails validation.
        """
        if self._settings_instance is None:
            if not self._loaded:
                try:
                    self.load_config()
                except ConfigurationError:
                    # If loading fails, create a default instance as fallback
                    logger.warning("Configuration loading failed. Returning default settings instance.")
                    try:
                        self._settings_instance = self.settings_cls()
                        return self._settings_instance
                    except Exception as e_default:
                        # If even default instantiation fails, re-raise critical error
                        logger.critical(f"Failed to create even default Settings object: {e_default}")
                        raise ConfigurationError("Could not create default settings instance") from e_default


            try:
                # Use dictionary unpacking to instantiate the dataclass
                # Dataclass validation happens implicitly here
                self._settings_instance = self.settings_cls(**self._config)
                logger.debug("Created settings instance from loaded configuration.")
            except TypeError as e:
                # Catches errors if required fields are missing or types are wrong
                logger.error(f"Failed to create Settings object from final configuration: {e}")
                logger.warning("Attempting to return default settings instance due to validation error.")
                try:
                    # Fallback to default instance on validation error
                    self._settings_instance = self.settings_cls()
                except Exception as e_default:
                     logger.critical(f"Failed to create fallback default Settings object: {e_default}")
                     raise ConfigurationError(f"Configuration validation failed and fallback failed: {e}") from e
            except Exception as e: # Catch other potential errors during instantiation
                 logger.error(f"Unexpected error creating Settings object: {e}")
                 raise ConfigurationError(f"Failed to create settings instance: {e}") from e

        # Ensure the return type hint matches the cached instance type
        return self._settings_instance # type: ignore[return-value]
