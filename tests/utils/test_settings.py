"""Tests for the settings module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from pytest_analyzer.utils.configuration import ConfigurationManager
from pytest_analyzer.utils.settings import Settings, load_settings


@pytest.fixture
def sample_settings():
    """Provide a sample Settings instance for testing."""
    return Settings(
        pytest_timeout=60,
        pytest_args=["--verbose"],
        max_memory_mb=2048,
        parser_timeout=15,
        analyzer_timeout=30,
        max_failures=50,
        preferred_format="xml",
        max_suggestions=5,
        min_confidence=0.7,
        project_root=Path("/project"),
        mock_directories={"/etc": "/mock/etc"},
    )


def test_settings_initialization():
    """Test initialization of Settings with default values."""
    # Create a Settings instance with default values
    settings = Settings()

    # Verify the default values
    assert settings.pytest_timeout == 300
    assert settings.pytest_args == []
    assert settings.max_memory_mb == 1024
    assert settings.parser_timeout == 30
    assert settings.analyzer_timeout == 60
    assert settings.max_failures == 100
    assert settings.preferred_format == "json"
    assert settings.max_suggestions == 3
    assert settings.min_confidence == 0.5
    assert settings.project_root == Path.cwd()
    assert settings.mock_directories == {}


def test_settings_initialization_with_values(sample_settings):
    """Test initialization of Settings with custom values."""
    # Verify the custom values
    assert sample_settings.pytest_timeout == 60
    assert sample_settings.pytest_args == ["--verbose"]
    assert sample_settings.max_memory_mb == 2048
    assert sample_settings.parser_timeout == 15
    assert sample_settings.analyzer_timeout == 30
    assert sample_settings.max_failures == 50
    assert sample_settings.preferred_format == "xml"
    assert sample_settings.max_suggestions == 5
    assert sample_settings.min_confidence == 0.7
    assert sample_settings.project_root == Path("/project")
    assert sample_settings.mock_directories == {"/etc": "/mock/etc"}


def test_settings_post_init_with_string_project_root():
    """Test post-initialization conversion of project_root from string to Path."""
    # Create a Settings instance with a string project_root
    settings = Settings(project_root="/project")

    # Verify that the project_root was converted to a Path
    assert isinstance(settings.project_root, Path)
    assert settings.project_root == Path("/project")


def test_settings_post_init_without_project_root():
    """Test post-initialization setting of project_root when not provided."""
    # Create a Settings instance without a project_root
    settings = Settings(project_root=None)

    # Verify that the project_root was set to the current working directory
    assert isinstance(settings.project_root, Path)
    assert settings.project_root == Path.cwd()


def test_load_settings_none():
    """Test loading settings from a None config file."""
    # Load settings from a None config file
    settings = load_settings(None)

    # Verify that default settings were returned
    assert isinstance(settings, Settings)
    assert settings.pytest_timeout == 300
    assert settings.max_memory_mb == 1024


def test_load_settings_nonexistent_file():
    """Test loading settings from a nonexistent file."""
    # Load settings from a nonexistent file
    with patch("pathlib.Path.exists", return_value=False):
        settings = load_settings("nonexistent_file.json")

    # Verify that default settings were returned
    assert isinstance(settings, Settings)
    assert settings.pytest_timeout == 300
    assert settings.max_memory_mb == 1024


def test_load_settings_existing_file():
    """Test loading settings from an existing file."""
    # In the current implementation, the load_settings function
    # doesn't actually parse the file content. It just returns
    # default settings if the file exists. In a real implementation,
    # it would parse the file and update the settings accordingly.

    # Load settings from an existing file
    with patch("pathlib.Path.exists", return_value=True):
        settings = load_settings("existing_file.json")

    # Verify that settings were returned
    assert isinstance(settings, Settings)


# Add these new test functions

VALID_ENV_MANAGERS = ["pixi", "poetry", "hatch", "uv", "pipenv", "pip+venv"]
VALID_ENV_MANAGERS_MIXED_CASE = ["PIXI", "Poetry", "Hatch", "Uv", "PipEnv", "PIP+VENV"]


@pytest.mark.parametrize("manager_name", VALID_ENV_MANAGERS)
def test_settings_post_init_environment_manager_valid_values(manager_name):
    """Test Settings initialization with valid environment_manager values."""
    settings = Settings(environment_manager=manager_name)
    assert settings.environment_manager == manager_name


@pytest.mark.parametrize("manager_name_mixed_case", VALID_ENV_MANAGERS_MIXED_CASE)
def test_settings_post_init_environment_manager_case_insensitive(
    manager_name_mixed_case,
):
    """Test Settings initialization with case-insensitive valid environment_manager values."""
    settings = Settings(environment_manager=manager_name_mixed_case)
    assert settings.environment_manager == manager_name_mixed_case.lower()


def test_settings_post_init_environment_manager_invalid_value():
    """Test Settings initialization with an invalid environment_manager value."""
    invalid_manager = "invalid_manager_value"
    with pytest.raises(
        ValueError,
        match=rf"Invalid environment_manager: '{invalid_manager}'. Must be one of .* \(case-insensitive\), or None.",
    ):
        Settings(environment_manager=invalid_manager)


def test_settings_post_init_environment_manager_none_value():
    """Test Settings initialization with environment_manager=None."""
    settings = Settings(environment_manager=None)
    assert settings.environment_manager is None


def test_settings_default_environment_manager():
    """Test that the default value for environment_manager is None."""
    settings = Settings()
    assert settings.environment_manager is None


@pytest.mark.parametrize("manager_name_mixed_case", VALID_ENV_MANAGERS_MIXED_CASE)
def test_config_manager_load_environment_manager_from_env(manager_name_mixed_case):
    """Test loading environment_manager from an environment variable."""
    env_var_value = manager_name_mixed_case
    expected_value = manager_name_mixed_case.lower()
    with patch.dict(os.environ, {"PYTEST_ANALYZER_ENVIRONMENT_MANAGER": env_var_value}):
        config_manager = ConfigurationManager()
        config_manager.load_config(force_reload=True)
        settings = config_manager.get_settings()
        assert settings.environment_manager == expected_value


def test_config_manager_load_invalid_environment_manager_from_env(caplog):
    """Test loading an invalid environment_manager from an environment variable falls back to default."""
    invalid_manager = "bad_env_manager"
    with patch.dict(
        os.environ, {"PYTEST_ANALYZER_ENVIRONMENT_MANAGER": invalid_manager}
    ):
        config_manager = ConfigurationManager()
        config_manager.load_config(force_reload=True)
        # Should not raise, but log an error and fall back to defaults
        settings = config_manager.get_settings()
        assert "Failed to validate final configuration" in caplog.text
        # The setting should have its default value
        assert settings.environment_manager is None


@pytest.mark.parametrize("manager_name_mixed_case", VALID_ENV_MANAGERS_MIXED_CASE)
def test_config_manager_load_environment_manager_from_yaml(
    tmp_path, manager_name_mixed_case
):
    """Test loading environment_manager from a YAML configuration file."""
    yaml_value = manager_name_mixed_case
    expected_value = manager_name_mixed_case.lower()
    config_content = f"environment_manager: {yaml_value}\n"
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(config_content)

    config_manager = ConfigurationManager(config_file_path=config_file)
    config_manager.load_config(force_reload=True)
    settings = config_manager.get_settings()
    assert settings.environment_manager == expected_value


def test_config_manager_load_invalid_environment_manager_from_yaml(tmp_path, caplog):
    """Test loading an invalid environment_manager from a YAML file falls back to default."""
    invalid_manager = "bad_yaml_manager"
    config_content = f"environment_manager: {invalid_manager}\n"
    config_file = tmp_path / "test_invalid_config.yaml"
    config_file.write_text(config_content)

    config_manager = ConfigurationManager(config_file_path=config_file)
    config_manager.load_config(force_reload=True)
    # Should not raise, but log an error and fall back to defaults
    settings = config_manager.get_settings()
    assert "Failed to validate final configuration" in caplog.text
    # The setting should have its default value
    assert settings.environment_manager is None


def test_config_manager_precedence_env_over_yaml_environment_manager(tmp_path):
    """Test that environment variable overrides YAML for environment_manager."""
    yaml_manager = "pipenv"
    env_manager = "uv"  # This should be the final value

    config_content = f"environment_manager: {yaml_manager}\n"
    config_file = tmp_path / "test_config_precedence.yaml"
    config_file.write_text(config_content)

    with patch.dict(os.environ, {"PYTEST_ANALYZER_ENVIRONMENT_MANAGER": env_manager}):
        config_manager = ConfigurationManager(config_file_path=config_file)
        config_manager.load_config(force_reload=True)
        settings = config_manager.get_settings()
        assert settings.environment_manager == env_manager.lower()


def test_config_manager_precedence_env_over_yaml_mixed_case_environment_manager(
    tmp_path,
):
    """Test that environment variable (mixed case) overrides YAML for environment_manager."""
    yaml_manager = "pipenv"
    env_manager_mixed_case = "UV"  # This should be the final value, normalized
    expected_env_manager = "uv"

    config_content = f"environment_manager: {yaml_manager}\n"
    config_file = tmp_path / "test_config_precedence_mixed.yaml"
    config_file.write_text(config_content)

    with patch.dict(
        os.environ, {"PYTEST_ANALYZER_ENVIRONMENT_MANAGER": env_manager_mixed_case}
    ):
        config_manager = ConfigurationManager(config_file_path=config_file)
        config_manager.load_config(force_reload=True)
        settings = config_manager.get_settings()
        assert settings.environment_manager == expected_env_manager


def test_config_manager_default_environment_manager_if_not_set():
    """Test that environment_manager is None by default if not set in env or file."""
    # Ensure the env var is not set for this test
    with patch.dict(os.environ, {}, clear=True):
        config_manager = ConfigurationManager(
            config_file_path=None
        )  # Explicitly no file
        # To be absolutely sure no default file is picked up, we can mock _resolve_config_file_path
        # or ensure the test runs in an environment where no default config file exists.
        # For simplicity, assuming no default config file with this setting is present.
        config_manager.load_config(force_reload=True)
        settings = config_manager.get_settings()
        assert settings.environment_manager is None
