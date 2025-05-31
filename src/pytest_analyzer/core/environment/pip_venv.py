"""
Pip + Venv environment manager implementation.

This module provides a concrete implementation of the EnvironmentManager
protocol for projects managed with Pip and a virtual environment (venv).
"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from .protocol import EnvironmentManager


class PipVenvManager(EnvironmentManager):
    """
    Manages Python environments using Pip and Venv.

    This manager attempts to locate a virtual environment (e.g., .venv, venv)
    and execute commands using executables from that environment's bin directory.
    It's often used as a fallback.
    """

    NAME: str = "PipVenv"
    COMMON_VENV_DIRS: List[str] = [".venv", "venv", "env"]

    def __init__(self, project_path: Path):
        """
        Initializes the PipVenvManager.

        Args:
            project_path: The root path of the project.
        """
        self.project_path = project_path
        self.venv_bin_path: Optional[Path] = self._find_venv_bin_path()

    def _get_bin_dir_name(self) -> str:
        """Returns the name of the binary directory based on OS."""
        return "Scripts" if os.name == "nt" else "bin"

    def _get_python_exe_name(self) -> str:
        """Returns the name of the python executable based on OS."""
        return "python.exe" if os.name == "nt" else "python"

    def _find_venv_bin_path(self) -> Optional[Path]:
        """
        Tries to find the bin directory of a virtual environment.
        Checks for common venv directory names and verifies a Python executable exists.
        """
        bin_dir_name = self._get_bin_dir_name()
        python_exe_name = self._get_python_exe_name()

        for venv_dir_name in self.COMMON_VENV_DIRS:
            potential_venv_path = self.project_path / venv_dir_name
            potential_bin_path = potential_venv_path / bin_dir_name
            if (
                potential_bin_path.is_dir()
                and (potential_bin_path / python_exe_name).is_file()
            ):
                return potential_bin_path
        return None

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        """
        Detect if a Pip+Venv setup is likely used.

        Checks for 'requirements.txt' or a common venv directory structure.

        Args:
            project_path: The root path of the project to check.

        Returns:
            True if detected, False otherwise.
        """
        if (project_path / "requirements.txt").is_file():
            return True

        # Use temporary instance methods for OS-specific names in classmethod
        # This is a bit of a workaround for accessing OS-specific logic
        # without instantiating fully or duplicating logic.
        # A static method could also be used.
        bin_dir_name = "Scripts" if os.name == "nt" else "bin"
        python_exe_name = "python.exe" if os.name == "nt" else "python"

        for venv_dir_name in cls.COMMON_VENV_DIRS:
            potential_venv_path = project_path / venv_dir_name
            potential_bin_path = potential_venv_path / bin_dir_name
            if (
                potential_bin_path.is_dir()
                and (potential_bin_path / python_exe_name).is_file()
            ):
                return True
        return False

    def build_command(self, command: List[str]) -> List[str]:
        """
        Builds a command, attempting to use executables from the detected venv.

        If a venv is found and the command's executable exists within its
        bin directory, the command is modified to use the full path to that
        executable. Otherwise, the original command is returned.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            A new list of strings for the command, potentially modified.
        """
        if not command:
            return []

        if self.venv_bin_path:
            executable_name = command[0]
            executable_path = self.venv_bin_path / executable_name

            if executable_path.is_file():
                return [str(executable_path)] + command[1:]

            if os.name == "nt":
                # Try with common Windows extensions if base name not found
                for ext in [".exe", ".cmd", ".bat"]:
                    if executable_name.endswith(ext):  # Already has an extension
                        break
                    win_executable_path = self.venv_bin_path / f"{executable_name}{ext}"
                    if win_executable_path.is_file():
                        return [str(win_executable_path)] + command[1:]

        return command

    def execute_command(self, command: List[str]) -> int:
        """
        Execute a command.

        The command should ideally be prepared by `build_command`.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            The exit code of the executed command, or -1 if command is empty.
        """
        if not command:
            # Consider raising ValueError for an empty command
            return -1
        return subprocess.call(command, cwd=self.project_path)

    def activate(self) -> None:
        """
        Activate the Pip+Venv environment.

        For this manager, activation is implicit: `build_command` resolves paths
        to executables within the venv. This method is a no-op.
        """
        pass

    def deactivate(self) -> None:
        """
        Deactivate the Pip+Venv environment.

        As activation is implicit, deactivation is also a no-op.
        """
        pass
