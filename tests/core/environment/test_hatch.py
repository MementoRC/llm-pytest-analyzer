"""
Tests for the HatchManager class.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.environment.hatch import HatchManager


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def hatch_project(project_path: Path) -> Path:
    """Create a Hatch project with pyproject.toml."""
    pyproject_toml = project_path / "pyproject.toml"
    pyproject_toml.write_text("""
[project]
name = "test-project"
version = "0.1.0"

[tool.hatch.version]
path = "src/test_project/__init__.py"

[tool.hatch.envs.default]
python = "3.9"
""")
    return project_path


class TestHatchManager:
    def test_detect_hatch_project_tool_hatch(self, hatch_project: Path):
        """Test that Hatch projects with [tool.hatch] are correctly detected."""
        assert HatchManager.detect(hatch_project)

    def test_detect_hatch_project_tool_hatch_dot(self, project_path: Path):
        """Test that Hatch projects with [tool.hatch.] are correctly detected."""
        pyproject_toml = project_path / "pyproject.toml"
        pyproject_toml.write_text("""
[project]
name = "test-project"
version = "0.1.0"

[tool.hatch.envs.test]
python = "3.9"
""")
        assert HatchManager.detect(project_path)

    def test_detect_non_hatch_project(self, project_path: Path):
        """Test that non-Hatch projects are not detected."""
        assert not HatchManager.detect(project_path)

    def test_detect_pyproject_without_hatch(self, project_path: Path):
        """Test pyproject.toml without [tool.hatch] section."""
        pyproject_toml = project_path / "pyproject.toml"
        pyproject_toml.write_text("[build-system]\nrequires = ['setuptools']")
        assert not HatchManager.detect(project_path)

    def test_build_command(self, hatch_project: Path):
        """Test command building."""
        manager = HatchManager(hatch_project)
        command = ["pytest", "--verbose"]
        result = manager.build_command(command)
        assert result == ["hatch", "run", "pytest", "--verbose"]

    @patch("subprocess.call")
    def test_execute_command(
        self, mock_subprocess_call: MagicMock, hatch_project: Path
    ):
        """Test command execution."""
        manager = HatchManager(hatch_project)
        command = ["hatch", "run", "pytest"]
        mock_subprocess_call.return_value = 0

        exit_code = manager.execute_command(command)

        assert exit_code == 0
        mock_subprocess_call.assert_called_once_with(command, cwd=hatch_project)

    def test_activate_is_noop(self, hatch_project: Path):
        """Test that activate() is a no-op."""
        manager = HatchManager(hatch_project)
        try:
            manager.activate()
        except Exception as e:
            pytest.fail(f"activate() raised an exception: {e}")

    def test_deactivate_is_noop(self, hatch_project: Path):
        """Test that deactivate() is a no-op."""
        manager = HatchManager(hatch_project)
        try:
            manager.deactivate()
        except Exception as e:
            pytest.fail(f"deactivate() raised an exception: {e}")
