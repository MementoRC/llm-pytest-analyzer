"""
Tests for the UVManager class.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.environment.uv import UVManager


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def uv_project_lock(project_path: Path) -> Path:
    """Create a UV project with uv.lock."""
    (project_path / "uv.lock").touch()
    return project_path


@pytest.fixture
def uv_project_pyproject(project_path: Path) -> Path:
    """Create a UV project with pyproject.toml containing [tool.uv]."""
    pyproject_toml = project_path / "pyproject.toml"
    pyproject_toml.write_text("""
[project]
name = "test-project"
version = "0.1.0"

[tool.uv]
""")
    return project_path


class TestUVManager:
    def test_detect_uv_lock(self, uv_project_lock: Path):
        """Test that UV projects with uv.lock are correctly detected."""
        assert UVManager.detect(uv_project_lock)

    def test_detect_uv_pyproject(self, uv_project_pyproject: Path):
        """Test that UV projects with [tool.uv] in pyproject.toml are correctly detected."""
        assert UVManager.detect(uv_project_pyproject)

    def test_detect_uv_pyproject_sources(self, project_path: Path):
        """Test that UV projects with [tool.uv.sources] in pyproject.toml are correctly detected."""
        pyproject_toml = project_path / "pyproject.toml"
        pyproject_toml.write_text("""
[project]
name = "test-project"
version = "0.1.0"

[tool.uv.sources]
""")
        assert UVManager.detect(project_path)

    def test_detect_non_uv_project(self, project_path: Path):
        """Test that non-UV projects are not detected."""
        assert not UVManager.detect(project_path)

    def test_detect_pyproject_without_uv(self, project_path: Path):
        """Test pyproject.toml without [tool.uv] section."""
        pyproject_toml = project_path / "pyproject.toml"
        pyproject_toml.write_text("[build-system]\nrequires = ['setuptools']")
        assert not UVManager.detect(project_path)

    def test_build_command(self, uv_project_lock: Path):
        """Test command building."""
        manager = UVManager(uv_project_lock)
        command = ["pytest", "--verbose"]
        result = manager.build_command(command)
        assert result == ["uv", "run", "pytest", "--verbose"]

    @patch("subprocess.call")
    def test_execute_command(
        self, mock_subprocess_call: MagicMock, uv_project_lock: Path
    ):
        """Test command execution."""
        manager = UVManager(uv_project_lock)
        command = ["uv", "run", "pytest"]
        mock_subprocess_call.return_value = 0

        exit_code = manager.execute_command(command)

        assert exit_code == 0
        mock_subprocess_call.assert_called_once_with(command, cwd=uv_project_lock)

    def test_activate_is_noop(self, uv_project_lock: Path):
        """Test that activate() is a no-op."""
        manager = UVManager(uv_project_lock)
        try:
            manager.activate()
        except Exception as e:
            pytest.fail(f"activate() raised an exception: {e}")

    def test_deactivate_is_noop(self, uv_project_lock: Path):
        """Test that deactivate() is a no-op."""
        manager = UVManager(uv_project_lock)
        try:
            manager.deactivate()
        except Exception as e:
            pytest.fail(f"deactivate() raised an exception: {e}")
