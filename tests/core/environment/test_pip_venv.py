"""
Tests for the PipVenvManager class.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.environment.pip_venv import PipVenvManager


@pytest.fixture
def project_path(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    return tmp_path


@pytest.fixture
def venv_project(project_path: Path) -> Path:
    """Create a project with a common venv directory."""
    venv_path = project_path / ".venv"
    bin_dir = venv_path / ("Scripts" if os.name == "nt" else "bin")
    bin_dir.mkdir(parents=True)
    (bin_dir / ("python.exe" if os.name == "nt" else "python")).touch()
    return project_path


@pytest.fixture
def reqs_project(project_path: Path) -> Path:
    """Create a project with requirements.txt."""
    (project_path / "requirements.txt").touch()
    return project_path


class TestPipVenvManagerDetect:
    """Tests for the PipVenvManager.detect() classmethod."""

    @patch("os.name", new_callable=lambda: "posix")
    def test_detect_venv_posix(self, mock_os_name: MagicMock, venv_project: Path):
        """Test detect() finds venv on POSIX."""
        assert PipVenvManager.detect(venv_project)

    @patch("os.name", new_callable=lambda: "nt")
    def test_detect_venv_windows(self, mock_os_name: MagicMock, project_path: Path):
        """Test detect() finds venv on Windows."""
        # Create Windows-specific venv structure after patching os.name
        venv_path = project_path / ".venv"
        bin_dir = venv_path / "Scripts"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python.exe").touch()

        assert PipVenvManager.detect(project_path)

    def test_detect_requirements_txt(self, reqs_project: Path):
        """Test detect() finds requirements.txt."""
        assert PipVenvManager.detect(reqs_project)

    def test_detect_non_pip_venv_project(self, project_path: Path):
        """Test detect() returns False for a non-Pip+Venv project."""
        assert not PipVenvManager.detect(project_path)

    @patch("os.name", new_callable=lambda: "posix")
    def test_detect_venv_no_python(self, mock_os_name: MagicMock, project_path: Path):
        """Test detect() returns False if venv bin exists but no python executable."""
        venv_path = project_path / "venv"
        bin_dir = venv_path / "bin"
        bin_dir.mkdir(parents=True)
        assert not PipVenvManager.detect(project_path)


class TestPipVenvManagerInitialization:
    """Tests for PipVenvManager.__init__()."""

    @patch.object(
        PipVenvManager, "_find_venv_bin_path", return_value=Path("/fake/venv/bin")
    )
    def test_init_stores_project_path_and_finds_venv(
        self, mock_find_venv: MagicMock, project_path: Path
    ):
        """Test that project_path is stored and _find_venv_bin_path is called."""
        manager = PipVenvManager(project_path)
        assert manager.project_path == project_path
        assert manager.venv_bin_path == Path("/fake/venv/bin")
        mock_find_venv.assert_called_once()

    @patch("os.name", new_callable=lambda: "posix")
    def test_find_venv_bin_path_posix(
        self, mock_os_name: MagicMock, venv_project: Path
    ):
        """Test _find_venv_bin_path finds the bin path on POSIX."""
        manager = PipVenvManager(venv_project)
        expected_path = venv_project / ".venv" / "bin"
        assert manager._find_venv_bin_path() == expected_path

    @patch("os.name", new_callable=lambda: "nt")
    def test_find_venv_bin_path_windows(
        self, mock_os_name: MagicMock, project_path: Path
    ):
        """Test _find_venv_bin_path finds the Scripts path on Windows."""
        # Create Windows-specific venv structure after patching os.name
        venv_path = project_path / ".venv"
        bin_dir = venv_path / "Scripts"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python.exe").touch()

        manager = PipVenvManager(project_path)
        expected_path = project_path / ".venv" / "Scripts"
        assert manager._find_venv_bin_path() == expected_path

    def test_find_venv_bin_path_not_found(self, project_path: Path):
        """Test _find_venv_bin_path returns None when no venv is found."""
        manager = PipVenvManager(project_path)
        assert manager._find_venv_bin_path() is None


class TestPipVenvManagerBuildCommand:
    """Tests for PipVenvManager.build_command()."""

    @patch("os.name", new_callable=lambda: "posix")
    def test_build_command_with_venv_executable_posix(
        self, mock_os_name: MagicMock, venv_project: Path
    ):
        """Test build_command uses venv executable path when found on POSIX."""
        manager = PipVenvManager(venv_project)
        # Ensure venv_bin_path is set correctly by init
        manager.venv_bin_path = venv_project / ".venv" / "bin"
        # Mock is_file to simulate executable existence
        with patch.object(Path, "is_file", return_value=True) as mock_is_file:
            command = ["pytest", "--verbose"]
            result = manager.build_command(command)
            expected_path = str(venv_project / ".venv" / "bin" / "pytest")
            assert result == [expected_path, "--verbose"]
            mock_is_file.assert_called_once_with()  # Check if pytest executable exists

    @patch("os.name", new_callable=lambda: "nt")
    def test_build_command_with_venv_executable_windows(
        self, mock_os_name: MagicMock, project_path: Path
    ):
        """Test build_command uses venv executable path when found on Windows."""
        # Create Windows-specific venv structure and executable after patching os.name
        venv_path = project_path / ".venv"
        bin_dir = venv_path / "Scripts"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python.exe").touch()  # Need python.exe for _find_venv_bin_path
        (bin_dir / "pytest.exe").touch()  # Create the executable we expect to find

        manager = PipVenvManager(project_path)  # Manager should find the venv now
        assert manager.venv_bin_path == bin_dir  # Verify venv was found

        command = ["pytest", "--verbose"]
        result = manager.build_command(command)
        expected_path = str(bin_dir / "pytest.exe")
        assert result == [expected_path, "--verbose"]

    @patch("os.name", new_callable=lambda: "nt")
    def test_build_command_with_venv_executable_windows_bat(
        self, mock_os_name: MagicMock, project_path: Path
    ):
        """Test build_command uses venv executable path with .bat on Windows."""
        # Create Windows-specific venv structure and executable after patching os.name
        venv_path = project_path / ".venv"
        bin_dir = venv_path / "Scripts"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python.exe").touch()  # Need python.exe for _find_venv_bin_path
        (bin_dir / "pytest.bat").touch()  # Create the executable we expect to find

        manager = PipVenvManager(project_path)  # Manager should find the venv now
        assert manager.venv_bin_path == bin_dir  # Verify venv was found

        command = ["pytest", "--verbose"]
        result = manager.build_command(command)
        expected_path = str(bin_dir / "pytest.bat")
        assert result == [expected_path, "--verbose"]

    def test_build_command_with_venv_executable_not_found(self, venv_project: Path):
        """Test build_command returns original command if executable not in venv bin."""
        manager = PipVenvManager(venv_project)
        manager.venv_bin_path = venv_project / ".venv" / "bin"  # Assume venv found
        with patch.object(Path, "is_file", return_value=False) as mock_is_file:
            command = ["some_other_command", "--flag"]
            result = manager.build_command(command)
            assert result == command  # Should return original command
            mock_is_file.assert_called_once()  # Should check for 'some_other_command'

    def test_build_command_without_venv(self, project_path: Path):
        """Test build_command returns original command if no venv is found."""
        manager = PipVenvManager(project_path)  # No venv created in this fixture
        assert manager.venv_bin_path is None
        command = ["pytest", "--verbose"]
        result = manager.build_command(command)
        assert result == command  # Should return original command

    def test_build_command_empty(self, project_path: Path):
        """Test build_command returns empty list for empty command."""
        manager = PipVenvManager(project_path)
        command = []
        result = manager.build_command(command)
        assert result == []


class TestPipVenvManagerExecuteCommand:
    """Tests for PipVenvManager.execute_command()."""

    @patch("subprocess.call")
    def test_execute_command_calls_subprocess_correctly(
        self, mock_subprocess_call: MagicMock, project_path: Path
    ):
        """Test execute_command() calls subprocess.call with the correct command and cwd."""
        manager = PipVenvManager(project_path)
        command_to_execute = ["/fake/venv/bin/pytest", "-k", "test_this"]
        mock_subprocess_call.return_value = 0  # Simulate successful execution

        manager.execute_command(command_to_execute)

        mock_subprocess_call.assert_called_once_with(
            command_to_execute, cwd=project_path
        )

    @patch("subprocess.call")
    def test_execute_command_returns_exit_code(
        self, mock_subprocess_call: MagicMock, project_path: Path
    ):
        """Test execute_command() returns the exit code from subprocess.call."""
        manager = PipVenvManager(project_path)
        command_to_execute = ["pytest", "some_arg"]
        expected_exit_code = 1
        mock_subprocess_call.return_value = expected_exit_code

        actual_exit_code = manager.execute_command(command_to_execute)

        assert actual_exit_code == expected_exit_code
        mock_subprocess_call.assert_called_once_with(
            command_to_execute, cwd=project_path
        )

    def test_execute_command_empty(self, project_path: Path):
        """Test execute_command() returns -1 for an empty command."""
        manager = PipVenvManager(project_path)
        exit_code = manager.execute_command([])
        assert exit_code == -1


class TestPipVenvManagerActivationDeactivation:
    """Tests for PipVenvManager.activate() and deactivate()."""

    def test_activate_is_noop(self, project_path: Path):
        """Test that activate() is a no-op and does not raise errors."""
        manager = PipVenvManager(project_path)
        try:
            manager.activate()
        except Exception as e:
            pytest.fail(f"activate() raised an exception: {e}")

    def test_deactivate_is_noop(self, project_path: Path):
        """Test that deactivate() is a no-op and does not raise errors."""
        manager = PipVenvManager(project_path)
        try:
            manager.deactivate()
        except Exception as e:
            pytest.fail(f"deactivate() raised an exception: {e}")
