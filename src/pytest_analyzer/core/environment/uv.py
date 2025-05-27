"""
UV environment manager implementation.

This module provides a concrete implementation of the EnvironmentManager
protocol for projects managed with UV.
"""

import subprocess
from pathlib import Path
from typing import List

from .protocol import EnvironmentManager


class UVManager(EnvironmentManager):
    """
    Manages Python environments using UV.

    This class implements the EnvironmentManager protocol to interact with
    UV environments, allowing for command execution and environment detection.
    """

    NAME: str = "UV"

    def __init__(self, project_path: Path):
        """
        Initializes the UVManager.

        Args:
            project_path: The root path of the UV-managed project.
        """
        self.project_path = project_path

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        """
        Detect if UV is used in the given project.

        Checks for 'uv.lock' file or 'pyproject.toml' with UV configuration.

        Args:
            project_path: The root path of the project to check.

        Returns:
            True if detected, False otherwise.
        """
        if (project_path / "uv.lock").is_file():
            return True

        pyproject_file = project_path / "pyproject.toml"
        if pyproject_file.is_file():
            try:
                content = pyproject_file.read_text(encoding="utf-8")
                # Checks for [tool.uv], [tool.uv.sources], etc.
                return "[tool.uv" in content
            except IOError:
                return False
        return False

    def build_command(self, command: List[str]) -> List[str]:
        """
        Build a command list to be executed with UV.

        Prepends ["uv", "run"] to the given command.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            A new list of strings representing the command ready for execution
            via 'uv run'.
        """
        return ["uv", "run"] + command

    def execute_command(self, command: List[str]) -> int:
        """
        Execute a command within the UV-managed environment.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            The exit code of the executed command.
        """
        return subprocess.call(command, cwd=self.project_path)

    def activate(self) -> None:
        """
        Activate the UV environment.

        `uv run` handles activation implicitly. This method is a no-op.
        """
        pass

    def deactivate(self) -> None:
        """
        Deactivate the UV environment.

        Deactivation is handled by `uv run` process termination. This is a no-op.
        """
        pass
