"""
Tests for the PoetryManager class.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.environment.poetry import PoetryManager


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def poetry_project(project_path: Path) -> Path:
    """Create a Poetry project with pyproject.toml."""
    pyproject_toml = project_path / "pyproject.toml"
    pyproject_toml.write_text("""
[tool.poetry]
name = "test-project"
version = "0.1.0"
description = ""
authors = ["Test Author <test@example.com>"]

[tool.poetry.dependencies]
python = "^3.8"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
""")
    return project_path


class TestPoetryManager:
    def test_detect_poetry_project(self, poetry_project: Path):
        """Test that Poetry projects are correctly detected."""
        assert PoetryManager.detect(poetry_project)

    def test_detect_non_poetry_project(self, project_path: Path):
        """Test that non-Poetry projects are not detected."""
        assert not PoetryManager.detect(project_path)

    def test_detect_pyproject_without_poetry(self, project_path: Path):
        """Test pyproject.toml without [tool.poetry] section."""
        pyproject_toml = project_path / "pyproject.toml"
        pyproject_toml.write_text("[build-system]\nrequires = ['setuptools']")
        assert not PoetryManager.detect(project_path)

    def test_build_command(self, poetry_project: Path):
        """Test command building."""
        manager = PoetryManager(poetry_project)
        command = ["pytest", "--verbose"]
        result = manager.build_command(command)
        assert result == ["poetry", "run", "pytest", "--verbose"]

    @patch("subprocess.call")
    def test_execute_command(
        self, mock_subprocess_call: MagicMock, poetry_project: Path
    ):
        """Test command execution."""
        manager = PoetryManager(poetry_project)
        command = ["poetry", "run", "pytest"]
        mock_subprocess_call.return_value = 0

        exit_code = manager.execute_command(command)

        assert exit_code == 0
        mock_subprocess_call.assert_called_once_with(command, cwd=poetry_project)

    def test_activate_is_noop(self, poetry_project: Path):
        """Test that activate() is a no-op."""
        manager = PoetryManager(poetry_project)
        try:
            manager.activate()
        except Exception as e:
            pytest.fail(f"activate() raised an exception: {e}")

    def test_deactivate_is_noop(self, poetry_project: Path):
        """Test that deactivate() is a no-op."""
        manager = PoetryManager(poetry_project)
        try:
            manager.deactivate()
        except Exception as e:
            pytest.fail(f"deactivate() raised an exception: {e}")
