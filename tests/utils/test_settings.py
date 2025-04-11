"""Tests for the settings module."""
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from src.pytest_analyzer.utils.settings import Settings, load_settings


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
        mock_directories={"/etc": "/mock/etc"}
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
    with patch('pathlib.Path.exists', return_value=False):
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
    with patch('pathlib.Path.exists', return_value=True):
        settings = load_settings("existing_file.json")
    
    # Verify that settings were returned
    assert isinstance(settings, Settings)