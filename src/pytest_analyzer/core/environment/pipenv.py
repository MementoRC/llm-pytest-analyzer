"""
Pipenv environment manager implementation.

This module provides a concrete implementation of the EnvironmentManager
protocol for projects managed with Pipenv.
"""

import subprocess
from pathlib import Path
from typing import List

from .protocol import EnvironmentManager


class PipenvManager(EnvironmentManager):
    """
    Manages Python environments using Pipenv.

    This class implements the EnvironmentManager protocol to interact with
    Pipenv environments, allowing for command execution and environment detection.
    """

    NAME: str = "Pipenv"

    def __init__(self, project_path: Path):
        """
        Initializes the PipenvManager.

        Args:
            project_path: The root path of the Pipenv-managed project.
        """
        self.project_path = project_path

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        """
        Detect if Pipenv is used in the given project.

        Checks for the presence of a 'Pipfile' or 'Pipfile.lock'.

        Args:
            project_path: The root path of the project to check.

        Returns:
            True if 'Pipfile' or 'Pipfile.lock' exists, False otherwise.
        """
        return (project_path / "Pipfile").is_file() or (
            project_path / "Pipfile.lock"
        ).is_file()

    def build_command(self, command: List[str]) -> List[str]:
        """
        Build a command list to be executed with Pipenv.

        Prepends ["pipenv", "run"] to the given command.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            A new list of strings representing the command ready for execution
            via 'pipenv run'.
        """
        return ["pipenv", "run"] + command

    def execute_command(self, command: List[str]) -> int:
        """
        Execute a command within the Pipenv-managed environment.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            The exit code of the executed command.
        """
        return subprocess.call(command, cwd=self.project_path)

    def activate(self) -> None:
        """
        Activate the Pipenv environment.

        `pipenv run` handles activation implicitly. This method is a no-op.
        """
        pass

    def deactivate(self) -> None:
        """
        Deactivate the Pipenv environment.

        Deactivation is handled by `pipenv run` process termination. This is a no-op.
        """
        pass
