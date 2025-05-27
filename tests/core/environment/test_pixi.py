"""
Tests for the PixiManager class.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.environment.pixi import PixiManager


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    """
    Provides a temporary directory path for a mock project.
    """
    return tmp_path


class TestPixiManagerDetect:
    """Tests for the PixiManager.detect() classmethod."""

    def test_detect_when_pixi_toml_exists(self, project_path: Path):
        """
        Test detect() returns True when pixi.toml exists in the project path.
        """
        (project_path / "pixi.toml").touch()
        assert PixiManager.detect(project_path) is True

    def test_detect_when_pixi_toml_does_not_exist(self, project_path: Path):
        """
        Test detect() returns False when pixi.toml does not exist.
        """
        assert PixiManager.detect(project_path) is False

    def test_detect_with_other_file_types(self, project_path: Path):
        """
        Test detect() returns False even if other 'pixi' related files exist,
        but not 'pixi.toml'.
        """
        (project_path / "pixi.lock").touch()
        (project_path / "pixi.txt").touch()
        assert PixiManager.detect(project_path) is False

    def test_detect_in_empty_directory(self, project_path: Path):
        """
        Test detect() returns False for an empty directory.
        """
        assert PixiManager.detect(project_path) is False


class TestPixiManagerInitialization:
    """Tests for PixiManager.__init__()."""

    def test_init_stores_project_path(self, project_path: Path):
        """
        Test that the project_path is correctly stored on initialization.
        """
        manager = PixiManager(project_path)
        assert manager.project_path == project_path


class TestPixiManagerBuildCommand:
    """Tests for PixiManager.build_command()."""

    def test_build_command_simple(self, project_path: Path):
        """
        Test build_command() with a simple command.
        """
        manager = PixiManager(project_path)
        command = ["pytest"]
        expected = ["pixi", "run", "pytest"]
        assert manager.build_command(command) == expected

    def test_build_command_with_arguments(self, project_path: Path):
        """
        Test build_command() with a command that includes arguments.
        """
        manager = PixiManager(project_path)
        command = ["pytest", "-v", "tests/"]
        expected = ["pixi", "run", "pytest", "-v", "tests/"]
        assert manager.build_command(command) == expected

    def test_build_command_empty(self, project_path: Path):
        """
        Test build_command() with an empty command list.
        """
        manager = PixiManager(project_path)
        command = []
        expected = ["pixi", "run"]
        assert manager.build_command(command) == expected


class TestPixiManagerExecuteCommand:
    """Tests for PixiManager.execute_command()."""

    @patch("subprocess.call")
    def test_execute_command_calls_subprocess_correctly(
        self, mock_subprocess_call: MagicMock, project_path: Path
    ):
        """
        Test execute_command() calls subprocess.call with the correct
        command and cwd.
        """
        manager = PixiManager(project_path)
        command_to_execute = ["pixi", "run", "pytest", "-k", "test_this"]
        mock_subprocess_call.return_value = 0  # Simulate successful execution

        manager.execute_command(command_to_execute)

        mock_subprocess_call.assert_called_once_with(
            command_to_execute, cwd=project_path
        )

    @patch("subprocess.call")
    def test_execute_command_returns_exit_code(
        self, mock_subprocess_call: MagicMock, project_path: Path
    ):
        """
        Test execute_command() returns the exit code from subprocess.call.
        """
        manager = PixiManager(project_path)
        command_to_execute = ["pixi", "run", "some_command"]
        expected_exit_code = 1
        mock_subprocess_call.return_value = expected_exit_code

        actual_exit_code = manager.execute_command(command_to_execute)

        assert actual_exit_code == expected_exit_code
        mock_subprocess_call.assert_called_once_with(
            command_to_execute, cwd=project_path
        )


class TestPixiManagerActivationDeactivation:
    """Tests for PixiManager.activate() and deactivate()."""

    def test_activate_is_noop(self, project_path: Path):
        """
        Test that activate() is a no-op and does not raise errors.
        """
        manager = PixiManager(project_path)
        try:
            manager.activate()
        except Exception as e:
            pytest.fail(f"activate() raised an exception: {e}")

    def test_deactivate_is_noop(self, project_path: Path):
        """
        Test that deactivate() is a no-op and does not raise errors.
        """
        manager = PixiManager(project_path)
        try:
            manager.deactivate()
        except Exception as e:
            pytest.fail(f"deactivate() raised an exception: {e}")


class TestPixiManagerIntegration:
    """Integration-style tests for PixiManager."""

    @patch("subprocess.call")
    def test_integration_build_and_execute(
        self, mock_subprocess_call: MagicMock, project_path: Path
    ):
        """
        Test the typical flow of building a command and then executing it.
        """
        (project_path / "pixi.toml").touch()  # Ensure detection would work
        assert PixiManager.detect(project_path)  # Sanity check detection

        manager = PixiManager(project_path)
        original_command = ["pytest", "--collect-only"]

        # Build the command
        full_command = manager.build_command(original_command)
        expected_full_command = ["pixi", "run", "pytest", "--collect-only"]
        assert full_command == expected_full_command

        # Execute the command
        mock_subprocess_call.return_value = 0  # Simulate success
        exit_code = manager.execute_command(full_command)

        assert exit_code == 0
        mock_subprocess_call.assert_called_once_with(
            expected_full_command, cwd=project_path
        )
