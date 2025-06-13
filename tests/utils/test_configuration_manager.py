"""
Tests for the enhanced ConfigurationManager with Pydantic support.

This module tests the ConfigurationManager class, including YAML loading,
environment variable processing, profile support, and schema export functionality.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pytest_analyzer.utils.config_types import Settings
from pytest_analyzer.utils.configuration import (
    ConfigurationError,
    ConfigurationManager,
    _deep_merge,
)


class TestDeepMerge:
    """Tests for the _deep_merge utility function."""

    def test_simple_merge(self):
        """Test simple dictionary merge."""
        source = {"a": 1, "b": 2}
        destination = {"c": 3}
        result = _deep_merge(source, destination)

        assert result == {"a": 1, "b": 2, "c": 3}
        assert destination == {"a": 1, "b": 2, "c": 3}  # destination is modified

    def test_overwrite_values(self):
        """Test that source values overwrite destination values."""
        source = {"a": 1, "b": 2}
        destination = {"a": 999, "c": 3}
        result = _deep_merge(source, destination)

        assert result == {"a": 1, "b": 2, "c": 3}

    def test_nested_merge(self):
        """Test merging nested dictionaries."""
        source = {"nested": {"a": 1, "b": 2}}
        destination = {"nested": {"b": 999, "c": 3}, "other": 4}
        result = _deep_merge(source, destination)

        expected = {"nested": {"a": 1, "b": 2, "c": 3}, "other": 4}
        assert result == expected

    def test_deep_nested_merge(self):
        """Test merging deeply nested dictionaries."""
        source = {"level1": {"level2": {"a": 1}}}
        destination = {"level1": {"level2": {"b": 2}, "other": 3}}
        result = _deep_merge(source, destination)

        expected = {"level1": {"level2": {"a": 1, "b": 2}, "other": 3}}
        assert result == expected

    def test_non_dict_overwrite(self):
        """Test that non-dict values are overwritten."""
        source = {"a": {"nested": 1}}
        destination = {"a": "string_value"}
        result = _deep_merge(source, destination)

        assert result == {"a": {"nested": 1}}


class TestConfigurationManager:
    """Tests for ConfigurationManager class."""

    def test_init_with_valid_settings_class(self):
        """Test initialization with valid Pydantic BaseModel."""
        manager = ConfigurationManager(settings_cls=Settings)
        assert manager.settings_cls == Settings
        assert manager.env_prefix == "PYTEST_ANALYZER_"
        assert manager._loaded is False

    def test_init_with_invalid_settings_class(self):
        """Test initialization with invalid settings class."""

        class NotABaseModel:
            pass

        with pytest.raises(TypeError) as exc_info:
            ConfigurationManager(settings_cls=NotABaseModel)
        assert "must be a Pydantic BaseModel" in str(exc_info.value)

    def test_init_with_custom_env_prefix(self):
        """Test initialization with custom environment prefix."""
        manager = ConfigurationManager(settings_cls=Settings, env_prefix="CUSTOM_")
        assert manager.env_prefix == "CUSTOM_"

    @patch.dict(os.environ, {"PYTEST_ANALYZER_PROFILE": "dev"})
    def test_init_with_profile_from_env(self):
        """Test initialization detects profile from environment."""
        manager = ConfigurationManager(settings_cls=Settings)
        assert manager.profile == "dev"

    @patch.dict(os.environ, {}, clear=True)
    def test_init_without_profile(self):
        """Test initialization without profile."""
        manager = ConfigurationManager(settings_cls=Settings)
        assert manager.profile is None

    def test_load_defaults(self):
        """Test loading default values from Pydantic model."""
        manager = ConfigurationManager(settings_cls=Settings)
        defaults = manager._load_defaults()

        assert isinstance(defaults, dict)
        assert defaults["pytest_timeout"] == 300
        assert defaults["llm_model"] == "auto"
        assert defaults["debug"] is False
        assert isinstance(defaults["mcp"], dict)
        assert defaults["mcp"]["transport_type"] == "stdio"

    def test_load_defaults_error_handling(self):
        """Test error handling in _load_defaults."""

        # Create a mock settings class that raises an error during instantiation
        class FailingSettings(Settings):
            def __init__(self, **kwargs):
                raise ValueError("Test error")

        manager = ConfigurationManager(settings_cls=FailingSettings)
        with pytest.raises(ConfigurationError) as exc_info:
            manager._load_defaults()
        assert "Could not initialize default settings" in str(exc_info.value)

    def test_load_single_yaml_file_valid(self):
        """Test loading valid YAML file."""
        yaml_content = """
pytest_timeout: 600
llm_model: gpt-4
debug: true
mcp:
  transport_type: http
  http_port: 9000
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            manager = ConfigurationManager(settings_cls=Settings)
            config = manager._load_single_yaml_file(Path(f.name))

            assert config["pytest_timeout"] == 600
            assert config["llm_model"] == "gpt-4"
            assert config["debug"] is True
            assert config["mcp"]["transport_type"] == "http"
            assert config["mcp"]["http_port"] == 9000

            # Cleanup
            os.unlink(f.name)

    def test_load_single_yaml_file_empty(self):
        """Test loading empty YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()

            manager = ConfigurationManager(settings_cls=Settings)
            config = manager._load_single_yaml_file(Path(f.name))

            assert config == {}

            # Cleanup
            os.unlink(f.name)

    def test_load_single_yaml_file_invalid_yaml(self):
        """Test loading invalid YAML file."""
        invalid_yaml = """
invalid: yaml: content:
  - missing
    - proper
  indentation
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(invalid_yaml)
            f.flush()

            manager = ConfigurationManager(settings_cls=Settings)
            with pytest.raises(ConfigurationError) as exc_info:
                manager._load_single_yaml_file(Path(f.name))
            assert "Invalid YAML format" in str(exc_info.value)

            # Cleanup
            os.unlink(f.name)

    def test_load_single_yaml_file_not_dict(self):
        """Test loading YAML file that doesn't contain a dictionary."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("- item1\n- item2\n")
            f.flush()

            manager = ConfigurationManager(settings_cls=Settings)
            config = manager._load_single_yaml_file(Path(f.name))

            assert config == {}

            # Cleanup
            os.unlink(f.name)

    def test_load_single_yaml_file_not_found(self):
        """Test loading non-existent YAML file."""
        manager = ConfigurationManager(settings_cls=Settings)
        config = manager._load_single_yaml_file(Path("/nonexistent/file.yaml"))
        assert config == {}

    def test_load_from_file_no_config_file(self):
        """Test _load_from_file when no config file is set."""
        manager = ConfigurationManager(settings_cls=Settings)
        manager._config_file_path = None
        config = manager._load_from_file()
        assert config == {}

    def test_load_from_file_with_base_config(self):
        """Test loading base configuration file."""
        yaml_content = """
pytest_timeout: 600
llm_model: gpt-4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            manager = ConfigurationManager(settings_cls=Settings)
            manager._config_file_path = Path(f.name)
            config = manager._load_from_file()

            assert config["pytest_timeout"] == 600
            assert config["llm_model"] == "gpt-4"

            # Cleanup
            os.unlink(f.name)

    def test_load_from_file_with_profile(self):
        """Test loading base config and profile-specific config."""
        base_yaml = """
pytest_timeout: 600
llm_model: gpt-4
debug: false
"""
        profile_yaml = """
pytest_timeout: 300
debug: true
"""
        # Create base config file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as base_f:
            base_f.write(base_yaml)
            base_f.flush()

            # Create profile config file
            base_path = Path(base_f.name)
            profile_path = base_path.with_name(
                f"{base_path.stem}.dev{base_path.suffix}"
            )

            with open(profile_path, "w") as profile_f:
                profile_f.write(profile_yaml)

            manager = ConfigurationManager(settings_cls=Settings)
            manager._config_file_path = base_path
            manager.profile = "dev"
            config = manager._load_from_file()

            # Profile should override base settings
            assert config["pytest_timeout"] == 300  # From profile
            assert config["llm_model"] == "gpt-4"  # From base
            assert config["debug"] is True  # From profile

            # Cleanup
            os.unlink(base_f.name)
            os.unlink(profile_path)

    @patch.dict(
        os.environ,
        {
            "PYTEST_ANALYZER_PYTEST_TIMEOUT": "900",
            "PYTEST_ANALYZER_LLM_MODEL": "claude-3",
            "PYTEST_ANALYZER_DEBUG": "true",
        },
    )
    def test_load_from_env_simple_fields(self):
        """Test loading simple fields from environment variables."""
        manager = ConfigurationManager(settings_cls=Settings)
        env_config = manager._load_from_env()

        assert env_config["pytest_timeout"] == 900
        assert env_config["llm_model"] == "claude-3"
        assert env_config["debug"] is True

    @patch.dict(
        os.environ,
        {
            "PYTEST_ANALYZER_MCP_TRANSPORT_TYPE": "http",
            "PYTEST_ANALYZER_MCP_HTTP_PORT": "9000",
            "PYTEST_ANALYZER_MCP_SECURITY_REQUIRE_AUTHENTICATION": "true",
        },
    )
    def test_load_from_env_nested_fields(self):
        """Test loading nested MCP fields from environment variables."""
        manager = ConfigurationManager(settings_cls=Settings)
        env_config = manager._load_from_env()

        assert "mcp" in env_config
        assert env_config["mcp"]["transport_type"] == "http"
        assert env_config["mcp"]["http_port"] == 9000
        assert "security" in env_config["mcp"]
        assert env_config["mcp"]["security"]["require_authentication"] is True

    @patch.dict(
        os.environ,
        {
            "PYTEST_ANALYZER_PYTEST_ARGS": "arg1,arg2,arg3",
            "PYTEST_ANALYZER_MOCK_DIRECTORIES": "key1=value1,key2=value2",
        },
    )
    def test_load_from_env_complex_types(self):
        """Test loading complex types (lists, dicts) from environment variables."""
        manager = ConfigurationManager(settings_cls=Settings)
        env_config = manager._load_from_env()

        assert env_config["pytest_args"] == ["arg1", "arg2", "arg3"]
        assert env_config["mock_directories"] == {"key1": "value1", "key2": "value2"}

    @patch.dict(os.environ, {"PYTEST_ANALYZER_INVALID_FIELD": "value"})
    def test_load_from_env_invalid_field(self):
        """Test that invalid environment variables are ignored."""
        manager = ConfigurationManager(settings_cls=Settings)
        env_config = manager._load_from_env()

        assert "invalid_field" not in env_config

    @patch.dict(os.environ, {"PYTEST_ANALYZER_PYTEST_TIMEOUT": "invalid_number"})
    def test_load_from_env_invalid_type_conversion(self):
        """Test handling of invalid type conversions."""
        manager = ConfigurationManager(settings_cls=Settings)
        env_config = manager._load_from_env()

        # Should not include the field with invalid conversion
        assert "pytest_timeout" not in env_config

    def test_convert_type_basic_types(self):
        """Test type conversion for basic types."""
        manager = ConfigurationManager(settings_cls=Settings)

        assert manager._convert_type("123", int) == 123
        assert manager._convert_type("123.45", float) == 123.45
        assert manager._convert_type("test", str) == "test"
        assert manager._convert_type("/test/path", Path) == Path("/test/path")

    def test_convert_type_boolean(self):
        """Test boolean type conversion."""
        manager = ConfigurationManager(settings_cls=Settings)

        # True values
        for true_val in ["true", "True", "1", "yes", "y", "on"]:
            assert manager._convert_type(true_val, bool) is True

        # False values
        for false_val in ["false", "False", "0", "no", "n", "off", "anything_else"]:
            assert manager._convert_type(false_val, bool) is False

    def test_convert_type_optional(self):
        """Test Optional type conversion."""
        from typing import Optional

        manager = ConfigurationManager(settings_cls=Settings)

        assert manager._convert_type("123", Optional[int]) == 123
        assert manager._convert_type("test", Optional[str]) == "test"

    def test_convert_type_list(self):
        """Test list type conversion."""
        from typing import List

        manager = ConfigurationManager(settings_cls=Settings)

        assert manager._convert_type("a,b,c", List[str]) == ["a", "b", "c"]
        assert manager._convert_type("1,2,3", List[int]) == [1, 2, 3]
        assert manager._convert_type("a, b , c ", List[str]) == [
            "a",
            "b",
            "c",
        ]  # Strips whitespace

    def test_convert_type_dict(self):
        """Test dict type conversion."""
        from typing import Dict

        manager = ConfigurationManager(settings_cls=Settings)

        result = manager._convert_type("key1=value1,key2=value2", Dict[str, str])
        assert result == {"key1": "value1", "key2": "value2"}

        result = manager._convert_type("a=1,b=2", Dict[str, int])
        assert result == {"a": 1, "b": 2}

    def test_convert_type_unsupported(self):
        """Test unsupported type conversion."""
        manager = ConfigurationManager(settings_cls=Settings)

        with pytest.raises(TypeError) as exc_info:
            manager._convert_type("value", complex)  # Complex numbers not supported
        assert "Unsupported type conversion" in str(exc_info.value)

    def test_load_config_success(self):
        """Test successful configuration loading."""
        yaml_content = """
pytest_timeout: 600
llm_model: gpt-4
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            with patch.dict(os.environ, {"PYTEST_ANALYZER_DEBUG": "true"}):
                manager = ConfigurationManager(
                    settings_cls=Settings, config_file_path=f.name
                )
                manager.load_config()

                assert manager._loaded is True
                assert manager._config["pytest_timeout"] == 600
                assert manager._config["llm_model"] == "gpt-4"
                assert manager._config["debug"] is True  # From env

            # Cleanup
            os.unlink(f.name)

    def test_load_config_no_reload_when_loaded(self):
        """Test that load_config doesn't reload when already loaded."""
        manager = ConfigurationManager(settings_cls=Settings)
        manager._loaded = True
        manager._config = {"test": "value"}

        manager.load_config()  # Should not reload
        assert manager._config == {"test": "value"}

    def test_load_config_force_reload(self):
        """Test force reload functionality."""
        manager = ConfigurationManager(settings_cls=Settings)
        manager._loaded = True
        manager._config = {"old": "value"}

        manager.load_config(force_reload=True)
        assert manager._loaded is True
        assert "old" not in manager._config  # Config should be fresh

    def test_get_settings_default(self):
        """Test getting settings with defaults."""
        # Use a non-existent config file path to ensure we get pure defaults
        manager = ConfigurationManager(
            settings_cls=Settings, config_file_path="/nonexistent/path/config.yaml"
        )
        settings = manager.get_settings()

        assert isinstance(settings, Settings)
        assert settings.pytest_timeout == 300
        assert settings.llm_model == "auto"

    def test_get_settings_with_overrides(self):
        """Test getting settings with runtime overrides."""
        manager = ConfigurationManager(settings_cls=Settings)
        overrides = {"pytest_timeout": 900, "debug": True}
        settings = manager.get_settings(overrides=overrides)

        assert isinstance(settings, Settings)
        assert settings.pytest_timeout == 900
        assert settings.debug is True
        assert settings.log_level == "DEBUG"  # Should be synced

    def test_get_settings_validation_error_fallback(self):
        """Test fallback to defaults when validation fails."""
        manager = ConfigurationManager(settings_cls=Settings)
        manager._loaded = True
        manager._config = {
            "pytest_timeout": "invalid_value"
        }  # Will cause validation error

        # Should fallback to defaults
        settings = manager.get_settings()
        assert isinstance(settings, Settings)
        assert settings.pytest_timeout == 300  # Default value

    def test_get_settings_caching(self):
        """Test that settings instance is cached."""
        manager = ConfigurationManager(settings_cls=Settings)
        settings1 = manager.get_settings()
        settings2 = manager.get_settings()

        assert settings1 is settings2  # Same instance

    def test_get_settings_no_caching_with_overrides(self):
        """Test that overrides bypass caching."""
        manager = ConfigurationManager(settings_cls=Settings)
        settings1 = manager.get_settings()
        settings2 = manager.get_settings(overrides={"debug": True})

        assert settings1 is not settings2  # Different instances
        assert settings1.debug != settings2.debug

    def test_export_schema_json(self):
        """Test schema export functionality."""
        manager = ConfigurationManager(settings_cls=Settings)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            manager.export_schema_json(f.name)

            # Read back the exported schema
            with open(f.name, "r") as read_f:
                schema = json.load(read_f)

            assert isinstance(schema, dict)
            assert schema["type"] == "object"
            assert "properties" in schema
            assert "pytest_timeout" in schema["properties"]
            assert "mcp" in schema["properties"]

            # Cleanup
            os.unlink(f.name)

    def test_export_schema_json_custom_indent(self):
        """Test schema export with custom indentation."""
        manager = ConfigurationManager(settings_cls=Settings)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            manager.export_schema_json(f.name, indent=4)

            # Read back the file content to check indentation
            with open(f.name, "r") as read_f:
                content = read_f.read()

            # Check that content is properly indented (contains multiple spaces)
            assert "    " in content  # 4-space indentation

            # Cleanup
            os.unlink(f.name)

    def test_export_schema_json_io_error(self):
        """Test schema export IO error handling."""
        manager = ConfigurationManager(settings_cls=Settings)

        # Try to write to a non-existent directory
        with pytest.raises(ConfigurationError) as exc_info:
            manager.export_schema_json("/nonexistent/path/schema.json")
        assert "Could not write schema file" in str(exc_info.value)


class TestConfigurationManagerIntegration:
    """Integration tests for ConfigurationManager."""

    def test_complete_configuration_loading_flow(self):
        """Test the complete configuration loading flow with all sources."""
        # Create YAML config
        yaml_content = """
pytest_timeout: 600
llm_model: gpt-4
debug: false
mcp:
  transport_type: http
  http_port: 8080
  security:
    max_requests_per_window: 200
"""

        # Create profile config
        profile_yaml = """
pytest_timeout: 300
debug: true
mcp:
  security:
    require_authentication: true
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as base_f:
            base_f.write(yaml_content)
            base_f.flush()

            base_path = Path(base_f.name)
            profile_path = base_path.with_name(
                f"{base_path.stem}.test{base_path.suffix}"
            )

            with open(profile_path, "w") as profile_f:
                profile_f.write(profile_yaml)

            # Set environment variables
            env_vars = {
                "PYTEST_ANALYZER_PROFILE": "test",
                "PYTEST_ANALYZER_LLM_PROVIDER": "anthropic",
                "PYTEST_ANALYZER_MCP_HTTP_PORT": "9000",  # Should override YAML
            }

            with patch.dict(os.environ, env_vars):
                manager = ConfigurationManager(
                    settings_cls=Settings, config_file_path=base_f.name
                )
                settings = manager.get_settings()

                # Test precedence: env > profile > base > defaults
                assert settings.pytest_timeout == 300  # From profile (overrides base)
                assert settings.llm_model == "gpt-4"  # From base
                assert settings.llm_provider == "anthropic"  # From env
                assert settings.debug is True  # From profile
                assert settings.log_level == "DEBUG"  # Synced with debug

                # Test nested MCP settings
                assert settings.mcp.transport_type == "http"  # From base
                assert settings.mcp.http_port == 9000  # From env (overrides all)
                assert (
                    settings.mcp.security.require_authentication is True
                )  # From profile
                assert settings.mcp.security.max_requests_per_window == 200  # From base

            # Cleanup
            os.unlink(base_f.name)
            os.unlink(profile_path)

    def test_schema_export_and_validation(self):
        """Test schema export and use for validation."""
        manager = ConfigurationManager(settings_cls=Settings)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # Export schema
            manager.export_schema_json(f.name)

            # Read schema
            with open(f.name, "r") as read_f:
                schema = json.load(read_f)

            # Validate that schema contains expected structure
            assert "properties" in schema
            properties = schema["properties"]

            # Check core properties
            assert "pytest_timeout" in properties
            assert properties["pytest_timeout"]["type"] == "integer"

            assert "llm_model" in properties
            assert properties["llm_model"]["type"] == "string"

            assert "debug" in properties
            assert properties["debug"]["type"] == "boolean"

            # Check nested MCP properties
            assert "mcp" in properties
            mcp_schema = properties["mcp"]
            assert (
                "$defs" in schema
                or "definitions" in schema
                or "properties" in mcp_schema
            )

            # Cleanup
            os.unlink(f.name)

    def test_error_recovery_and_fallbacks(self):
        """Test error recovery and fallback mechanisms."""
        # Test with invalid YAML that should fallback to defaults
        invalid_yaml = "invalid: yaml: content: ["

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(invalid_yaml)
            f.flush()

            manager = ConfigurationManager(
                settings_cls=Settings, config_file_path=f.name
            )

            # Should not raise an error, but use defaults
            settings = manager.get_settings()
            assert isinstance(settings, Settings)
            assert settings.pytest_timeout == 300  # Default value

            # Cleanup
            os.unlink(f.name)

    def test_runtime_configuration_updates(self):
        """Test runtime configuration updates with overrides."""
        # Use a non-existent config file path to ensure we get pure defaults
        manager = ConfigurationManager(
            settings_cls=Settings, config_file_path="/nonexistent/path/config.yaml"
        )

        # Get initial settings
        initial_settings = manager.get_settings()
        assert initial_settings.pytest_timeout == 300
        assert initial_settings.debug is False

        # Apply runtime overrides
        runtime_overrides = {
            "pytest_timeout": 900,
            "debug": True,
            "mcp": {
                "transport_type": "http",
                "security": {"require_authentication": True},
            },
        }

        updated_settings = manager.get_settings(overrides=runtime_overrides)

        # Verify overrides are applied
        assert updated_settings.pytest_timeout == 900
        assert updated_settings.debug is True
        assert updated_settings.log_level == "DEBUG"
        assert updated_settings.mcp.transport_type == "http"
        assert updated_settings.mcp.security.require_authentication is True

        # Verify original cached settings are unchanged
        original_cached = manager.get_settings()
        assert original_cached.pytest_timeout == 300
        assert original_cached.debug is False
