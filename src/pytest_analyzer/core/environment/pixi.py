"""
Pixi environment manager implementation.

This module provides a concrete implementation of the EnvironmentManager
protocol for projects managed with Pixi.
"""

import subprocess
from pathlib import Path
from typing import List

from .protocol import EnvironmentManager


class PixiManager(EnvironmentManager):
    """
    Manages Python environments using Pixi.

    This class implements the EnvironmentManager protocol to interact with
    Pixi environments, allowing for command execution and environment detection.
    """

    NAME: str = "Pixi"

    def __init__(self, project_path: Path):
        """
        Initializes the PixiManager.

        Args:
            project_path: The root path of the Pixi-managed project.
        """
        self.project_path = project_path

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        """
        Detect if Pixi is used in the given project.

        Checks for the presence of a 'pixi.toml' file in the project root.

        Args:
            project_path: The root path of the project to check.

        Returns:
            True if 'pixi.toml' exists, False otherwise.
        """
        return (project_path / "pixi.toml").is_file()

    def build_command(self, command: List[str]) -> List[str]:
        """
        Build a command list to be executed with Pixi.

        Prepends ["pixi", "run"] to the given command.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            A new list of strings representing the command ready for execution
            via 'pixi run'.
        """
        return ["pixi", "run"] + command

    def execute_command(self, command: List[str]) -> int:
        """
        Execute a command within the Pixi-managed environment.

        Uses `subprocess.call` to run the command, which is expected to
        be built using `build_command` first.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            The exit code of the executed command.
        """
        # Ensure the command is run from the project's root directory
        # where pixi.toml is located.
        return subprocess.call(command, cwd=self.project_path)

    def activate(self) -> None:
        """
        Activate the Pixi environment.

        For Pixi, `pixi run` typically handles environment activation implicitly.
        Therefore, this method is a no-op.
        """
        pass  # Pixi handles activation via `pixi run`

    def deactivate(self) -> None:
        """
        Deactivate the Pixi environment.

        Similar to activation, deactivation is generally handled by the termination
        of the `pixi run` process. This method is a no-op.
        """
        pass  # Pixi handles deactivation implicitly
