"""Tests for the path resolver utilities."""
import pytest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.pytest_analyzer.utils.path_resolver import PathResolver


@pytest.fixture
def project_root(tmp_path):
    """Provide a temporary project root for testing."""
    return tmp_path


@pytest.fixture
def mock_dirs(project_root):
    """Provide mock directory mappings for testing."""
    return {
        "/absolute/path": project_root / "mocked" / "absolute_path",
        "/etc": project_root / "mocked" / "etc"
    }


@pytest.fixture
def path_resolver(project_root, mock_dirs):
    """Provide a PathResolver instance for testing."""
    return PathResolver(project_root=project_root, mock_dirs=mock_dirs)


def test_initialization(project_root, mock_dirs):
    """Test initialization of PathResolver."""
    # Create a resolver with the test fixtures
    resolver = PathResolver(project_root=project_root, mock_dirs=mock_dirs)
    
    # Verify the properties
    assert resolver.project_root == project_root
    assert resolver.mock_dirs == mock_dirs
    assert resolver.mock_root == project_root / "mocked"
    
    # Verify that the mock_root directory was created
    assert resolver.mock_root.exists()
    assert resolver.mock_root.is_dir()


def test_initialization_defaults():
    """Test initialization of PathResolver with default arguments."""
    # Create a resolver with default arguments
    resolver = PathResolver()
    
    # Verify the properties
    assert resolver.project_root == Path.cwd()
    assert resolver.mock_dirs == {}
    assert resolver.mock_root == Path.cwd() / "mocked"


def test_resolve_path_empty(path_resolver, project_root):
    """Test resolving an empty path."""
    # Resolve an empty path
    resolved = path_resolver.resolve_path("")
    
    # Verify the result
    assert resolved == project_root


def test_resolve_path_relative(path_resolver, project_root):
    """Test resolving a relative path."""
    # Resolve a relative path
    resolved = path_resolver.resolve_path("relative/path")
    
    # Verify the result
    assert resolved == (project_root / "relative/path").resolve()


def test_resolve_path_absolute_mock_mapping(path_resolver, project_root, mock_dirs):
    """Test resolving an absolute path with a mock mapping."""
    # Resolve an absolute path with a mock mapping
    resolved = path_resolver.resolve_path("/absolute/path/file.txt")
    
    # Verify the result
    expected = mock_dirs["/absolute/path"] / "file.txt"
    assert resolved == expected


def test_resolve_path_absolute_no_mapping(path_resolver, project_root):
    """Test resolving an absolute path without a mock mapping."""
    # Resolve an absolute path without a mock mapping
    resolved = path_resolver.resolve_path("/unmapped/path/file.txt")
    
    # Verify the result
    assert resolved == project_root / "mocked" / "unmapped" / "path" / "file.txt"
    
    # Verify that the parent directory was created
    assert resolved.parent.exists()
    assert resolved.parent.is_dir()


def test_relativize_within_project(path_resolver, project_root):
    """Test relativizing a path within the project root."""
    # Create a path within the project root
    path = project_root / "subdir" / "file.txt"
    
    # Relativize the path
    relative = path_resolver.relativize(path)
    
    # Verify the result
    assert relative == Path("subdir/file.txt")


def test_relativize_outside_project(path_resolver, project_root):
    """Test relativizing a path outside the project root."""
    # Create a path outside the project root
    path = Path("/outside/project/file.txt")
    
    # Relativize the path
    relative = path_resolver.relativize(path)
    
    # Verify the result
    assert relative == path


def test_relativize_mocked_path(path_resolver, project_root, mock_dirs):
    """Test relativizing a mocked path."""
    # Create a path in the mock directory
    mock_path = mock_dirs["/absolute/path"] / "file.txt"
    
    # Relativize the path
    relative = path_resolver.relativize(mock_path)
    
    # Verify the result
    assert relative == Path("/absolute/path/file.txt")


def test_relativize_non_path(path_resolver):
    """Test relativizing a string instead of a Path."""
    # Relativize a string
    relative = path_resolver.relativize("/some/path/file.txt")
    
    # Verify the result
    assert isinstance(relative, Path)