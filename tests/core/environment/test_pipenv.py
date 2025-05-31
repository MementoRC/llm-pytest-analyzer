"""
Tests for the PipenvManager class.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.environment.pipenv import PipenvManager


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def pipenv_project_pipfile(project_path: Path) -> Path:
    """Create a Pipenv project with Pipfile."""
    (project_path / "Pipfile").touch()
    return project_path


@pytest.fixture
def pipenv_project_lock(project_path: Path) -> Path:
    """Create a Pipenv project with Pipfile.lock."""
    (project_path / "Pipfile.lock").touch()
    return project_path


class TestPipenvManager:
    def test_detect_pipfile(self, pipenv_project_pipfile: Path):
        """Test that Pipenv projects with Pipfile are correctly detected."""
        assert PipenvManager.detect(pipenv_project_pipfile)

    def test_detect_pipfile_lock(self, pipenv_project_lock: Path):
        """Test that Pipenv projects with Pipfile.lock are correctly detected."""
        assert PipenvManager.detect(pipenv_project_lock)

    def test_detect_non_pipenv_project(self, project_path: Path):
        """Test that non-Pipenv projects are not detected."""
        assert not PipenvManager.detect(project_path)

    def test_build_command(self, pipenv_project_pipfile: Path):
        """Test command building."""
        manager = PipenvManager(pipenv_project_pipfile)
        command = ["pytest", "--verbose"]
        result = manager.build_command(command)
        assert result == ["pipenv", "run", "pytest", "--verbose"]

    @patch("subprocess.call")
    def test_execute_command(
        self, mock_subprocess_call: MagicMock, pipenv_project_pipfile: Path
    ):
        """Test command execution."""
        manager = PipenvManager(pipenv_project_pipfile)
        command = ["pipenv", "run", "pytest"]
        mock_subprocess_call.return_value = 0

        exit_code = manager.execute_command(command)

        assert exit_code == 0
        mock_subprocess_call.assert_called_once_with(
            command, cwd=pipenv_project_pipfile
        )

    def test_activate_is_noop(self, pipenv_project_pipfile: Path):
        """Test that activate() is a no-op."""
        manager = PipenvManager(pipenv_project_pipfile)
        try:
            manager.activate()
        except Exception as e:
            pytest.fail(f"activate() raised an exception: {e}")

    def test_deactivate_is_noop(self, pipenv_project_pipfile: Path):
        """Test that deactivate() is a no-op."""
        manager = PipenvManager(pipenv_project_pipfile)
        try:
            manager.deactivate()
        except Exception as e:
            pytest.fail(f"deactivate() raised an exception: {e}")
