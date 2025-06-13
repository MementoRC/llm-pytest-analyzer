import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

import yaml
from pydantic import BaseModel, ValidationError

# Import Settings from the config_types module to avoid circular dependency
from .config_types import Settings

logger = logging.getLogger(__name__)


# --- Configuration Manager ---


# Define a specific exception for configuration errors
class ConfigurationError(Exception):
    """Custom exception for configuration loading errors."""

    pass


def _deep_merge(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deeply merge two dictionaries. `source` is merged into `destination`.
    """
    for key, value in source.items():
        if (
            isinstance(value, dict)
            and key in destination
            and isinstance(destination[key], dict)
        ):
            destination[key] = _deep_merge(value, destination[key])
        else:
            destination[key] = value
    return destination


class ConfigurationManager:
    """
    Manages loading configuration settings from multiple sources using Pydantic.

    Handles hierarchical loading:
    1. Default values from the Pydantic Settings model.
    2. Values from a base YAML configuration file (e.g., pytest-analyzer.yaml).
    3. Values from a profile-specific YAML file (e.g., pytest-analyzer.dev.yaml).
    4. Values from environment variables.
    5. Runtime overrides.
    """

    DEFAULT_CONFIG_FILES = ["pytest-analyzer.yaml", "pytest-analyzer.yml"]
    ENV_PREFIX = "PYTEST_ANALYZER_"

    def __init__(
        self,
        settings_cls: Type[Settings] = Settings,
        config_file_path: Optional[Union[str, Path]] = None,
        env_prefix: str = ENV_PREFIX,
    ):
        """
        Initialize the ConfigurationManager.

        Args:
            settings_cls: The Pydantic BaseModel class for settings structure.
            config_file_path: Optional path to a specific configuration file.
                               If None, searches for default files.
            env_prefix: Prefix for environment variables.
        """
        if not issubclass(settings_cls, BaseModel):
            raise TypeError(f"{settings_cls.__name__} must be a Pydantic BaseModel.")

        self.settings_cls: Type[Settings] = settings_cls
        self.env_prefix: str = env_prefix
        self.profile: Optional[str] = os.getenv(f"{self.env_prefix}PROFILE")
        self._config_file_path: Optional[Path] = self._resolve_config_file_path(
            config_file_path
        )
        self._config: Dict[str, Any] = {}
        self._loaded: bool = False
        self._settings_instance: Optional[Settings] = None

    def _resolve_config_file_path(
        self, specific_path: Optional[Union[str, Path]]
    ) -> Optional[Path]:
        """Find the configuration file path."""
        search_paths: List[Path] = []

        if specific_path:
            p = Path(specific_path)
            if p.is_file():
                logger.debug(f"Using specified configuration file: {p}")
                return p
            else:
                logger.warning(
                    f"Specified configuration file not found: {specific_path}"
                )

        cwd = Path.cwd()
        search_paths.extend(cwd / name for name in self.DEFAULT_CONFIG_FILES)

        current = cwd.parent
        home = Path.home()
        while current != current.parent and current != home:
            search_paths.extend(current / name for name in self.DEFAULT_CONFIG_FILES)
            current = current.parent
        if home != cwd and home != cwd.parent:
            search_paths.extend(home / name for name in self.DEFAULT_CONFIG_FILES)

        for path in search_paths:
            try:
                resolved_path = path.resolve()
                if resolved_path.is_file():
                    logger.debug(f"Found configuration file: {resolved_path}")
                    return resolved_path
            except OSError as e:
                logger.debug(f"Could not access potential config file {path}: {e}")

        logger.debug("No configuration file found in standard locations.")
        return None

    def load_config(self, force_reload: bool = False) -> None:
        """Load configuration from all sources."""
        if self._loaded and not force_reload:
            return

        self._config = {}
        self._settings_instance = None

        try:
            defaults = self._load_defaults()
            file_config = self._load_from_file()
            env_config = self._load_from_env()

            # Merge with precedence: defaults < file < env
            self._config = defaults
            _deep_merge(file_config, self._config)
            _deep_merge(env_config, self._config)

            self._loaded = True
            logger.debug("Configuration loaded successfully.")
        except Exception as e:
            self._loaded = False
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigurationError("Configuration loading failed") from e

    def _load_defaults(self) -> Dict[str, Any]:
        """Load default values from the Pydantic Settings model."""
        try:
            defaults = self.settings_cls().model_dump()
            logger.debug("Loaded defaults from Pydantic model.")
            return defaults
        except Exception as e:
            logger.error(
                f"Critical error getting defaults from {self.settings_cls.__name__}: {e}"
            )
            raise ConfigurationError(
                f"Could not initialize default settings: {e}"
            ) from e

    def _load_single_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load configuration from a single YAML file."""
        try:
            with open(file_path, "r") as f:
                file_config = yaml.safe_load(f)
                if file_config and isinstance(file_config, dict):
                    logger.info(f"Loaded configuration from file: {file_path}")
                    return file_config
                elif file_config is not None:
                    logger.warning(
                        f"Configuration file {file_path} does not contain a dictionary."
                    )
                return {}
        except FileNotFoundError:
            logger.debug(f"Configuration file not found: {file_path}")
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration file {file_path}: {e}")
            raise ConfigurationError(f"Invalid YAML format in {file_path}") from e
        except Exception as e:
            logger.error(f"Error reading configuration file {file_path}: {e}")
            raise ConfigurationError(f"Could not read file {file_path}") from e
        return {}

    def _load_from_file(self) -> Dict[str, Any]:
        """Load configuration from base and profile-specific YAML files."""
        config = {}
        if self._config_file_path:
            config = self._load_single_yaml_file(self._config_file_path)

        if self.profile and self._config_file_path:
            profile_path = self._config_file_path.with_name(
                f"{self._config_file_path.stem}.{self.profile}{self._config_file_path.suffix}"
            )
            if profile_path.is_file():
                profile_config = self._load_single_yaml_file(profile_path)
                _deep_merge(profile_config, config)
            else:
                logger.debug(f"Profile config file not found: {profile_path}")

        return config

    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        env_config: Dict[str, Any] = {}
        model_fields = self.settings_cls.model_fields

        for env_var, value in os.environ.items():
            if not env_var.startswith(self.env_prefix):
                continue

            key_str = env_var[len(self.env_prefix) :].lower()
            parts = key_str.split("_")
            top_level_key = parts[0]

            field_info = model_fields.get(top_level_key)
            is_nested = (
                field_info
                and (
                    (
                        isinstance(
                            getattr(field_info.annotation, "__origin__", None),
                            type(Union),
                        )  # Handles Optional[BaseModel]
                        and any(
                            isinstance(arg, type) and issubclass(arg, BaseModel)
                            for arg in getattr(field_info.annotation, "__args__", [])
                        )
                    )
                    or (
                        isinstance(field_info.annotation, type)
                        and issubclass(field_info.annotation, BaseModel)
                    )
                )
                and len(parts) > 1
            )

            if is_nested:
                # Extract the nested model class from the annotation
                if isinstance(
                    getattr(field_info.annotation, "__origin__", None), type(Union)
                ):
                    # Handle Optional[BaseModel] case
                    nested_model_cls = next(
                        (
                            arg
                            for arg in getattr(field_info.annotation, "__args__", [])
                            if isinstance(arg, type) and issubclass(arg, BaseModel)
                        ),
                        None,
                    )
                elif isinstance(field_info.annotation, type) and issubclass(
                    field_info.annotation, BaseModel
                ):
                    # Handle direct BaseModel case
                    nested_model_cls = field_info.annotation
                else:
                    nested_model_cls = None

                if nested_model_cls and len(parts) >= 2:
                    # Try to match field names by rebuilding from parts
                    # This handles cases like mcp_transport_type -> transport_type
                    remaining_parts = parts[1:]  # Everything after the top-level key

                    # First, try to find a direct field match by joining all remaining parts
                    candidate_field = "_".join(remaining_parts)
                    if candidate_field in nested_model_cls.model_fields:
                        # Direct match: mcp_transport_type -> transport_type
                        target_type = nested_model_cls.model_fields[
                            candidate_field
                        ].annotation
                        try:
                            typed_value = self._convert_type(value, target_type)
                            env_config.setdefault(top_level_key, {})[
                                candidate_field
                            ] = typed_value
                            logger.debug(
                                f"Loaded nested env var '{env_var}' as '{top_level_key}.{candidate_field}'."
                            )
                            continue
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Could not convert env var {env_var}: {e}")
                            continue

                    # If no direct match, try nested approach (e.g., mcp_security_require_authentication)
                    if len(remaining_parts) >= 2:
                        second_level_key = remaining_parts[0]
                        third_level_parts = remaining_parts[1:]

                        second_level_field = nested_model_cls.model_fields.get(
                            second_level_key
                        )
                        if second_level_field:
                            # Get the nested model class for the second level
                            second_nested_cls = None
                            annotation = second_level_field.annotation
                            if isinstance(
                                getattr(annotation, "__origin__", None), type(Union)
                            ):
                                second_nested_cls = next(
                                    (
                                        arg
                                        for arg in getattr(annotation, "__args__", [])
                                        if isinstance(arg, type)
                                        and issubclass(arg, BaseModel)
                                    ),
                                    None,
                                )
                            elif isinstance(annotation, type) and issubclass(
                                annotation, BaseModel
                            ):
                                second_nested_cls = annotation

                            if second_nested_cls:
                                third_level_key = "_".join(third_level_parts)
                                if third_level_key in second_nested_cls.model_fields:
                                    target_type = second_nested_cls.model_fields[
                                        third_level_key
                                    ].annotation
                                    try:
                                        typed_value = self._convert_type(
                                            value, target_type
                                        )
                                        env_config.setdefault(
                                            top_level_key, {}
                                        ).setdefault(second_level_key, {})[
                                            third_level_key
                                        ] = typed_value
                                        logger.debug(
                                            f"Loaded nested env var '{env_var}' as '{top_level_key}.{second_level_key}.{third_level_key}'."
                                        )
                                        continue
                                    except (ValueError, TypeError) as e:
                                        logger.warning(
                                            f"Could not convert env var {env_var}: {e}"
                                        )
                                        continue
            elif key_str in model_fields:
                target_type = model_fields[key_str].annotation
                try:
                    typed_value = self._convert_type(value, target_type)
                    env_config[key_str] = typed_value
                    logger.debug(f"Loaded env var '{env_var}' as '{key_str}'.")
                except (ValueError, TypeError) as e:
                    logger.warning(f"Could not convert env var {env_var}: {e}")
        return env_config

    def _convert_type(self, value: str, target_type: Any) -> Any:
        """Convert string value to the target type."""
        origin_type = getattr(target_type, "__origin__", None)
        args = getattr(target_type, "__args__", [])

        if target_type is bool:
            return value.lower() in ("true", "1", "yes", "y", "on")
        elif target_type is int:
            return int(value)
        elif target_type is float:
            return float(value)
        elif target_type is Path:
            return Path(value)
        elif target_type is str:
            return value
        elif origin_type is Union and type(None) in args:
            non_none_type = next((t for t in args if t is not type(None)), str)
            return self._convert_type(value, non_none_type)
        elif origin_type is list or target_type is List:
            element_type = args[0] if args else str
            return [
                self._convert_type(item.strip(), element_type)
                for item in value.split(",")
                if item.strip()
            ]
        elif origin_type is dict or target_type is Dict:
            key_type = args[0] if args else str
            value_type = args[1] if len(args) > 1 else str
            result_dict = {}
            for item in value.split(","):
                if "=" in item:
                    k, v = item.split("=", 1)
                    result_dict[self._convert_type(k.strip(), key_type)] = (
                        self._convert_type(v.strip(), value_type)
                    )
            return result_dict

        try:
            return target_type(value)
        except (ValueError, TypeError):
            raise TypeError(
                f"Unsupported type conversion for {target_type} from string."
            )

    def get_settings(self, overrides: Optional[Dict[str, Any]] = None) -> Settings:
        """
        Return the final configuration as a validated Pydantic Settings object.

        Args:
            overrides: A dictionary of settings to apply on top of all other sources.

        Returns:
            An instance of the settings_cls populated with the merged configuration.

        Raises:
            ConfigurationError: If configuration fails validation and fallback fails.
        """
        if overrides is None and self._settings_instance is not None:
            return self._settings_instance

        if not self._loaded:
            try:
                self.load_config()
            except ConfigurationError:
                logger.warning(
                    "Configuration loading failed. Attempting to use defaults."
                )
                self._config = self._load_defaults()

        final_config = self._config.copy()
        if overrides:
            final_config = _deep_merge(overrides, final_config)

        try:
            instance = self.settings_cls.model_validate(final_config)
            if overrides is None:
                self._settings_instance = instance
            logger.debug("Created settings instance from loaded configuration.")
            return instance
        except ValidationError as e:
            logger.error(f"Failed to validate final configuration: {e}")
            logger.warning(
                "Attempting to return default settings instance due to validation error."
            )
            try:
                default_instance = self.settings_cls()
                if overrides is None:
                    self._settings_instance = default_instance
                return default_instance
            except Exception as e_default:
                logger.critical(
                    f"Failed to create fallback default Settings object: {e_default}"
                )
                raise ConfigurationError(
                    f"Configuration validation failed and fallback failed: {e}"
                ) from e

    def export_schema_json(self, path: Union[str, Path], indent: int = 2) -> None:
        """
        Export the Pydantic model schema to a JSON file.

        Args:
            path: The file path to save the schema to.
            indent: The JSON indentation level.
        """
        schema = self.settings_cls.model_json_schema()
        try:
            with open(path, "w") as f:
                json.dump(schema, f, indent=indent)
            logger.info(f"Configuration schema exported successfully to {path}")
        except IOError as e:
            logger.error(f"Failed to write schema to {path}: {e}")
            raise ConfigurationError(f"Could not write schema file: {e}") from e
