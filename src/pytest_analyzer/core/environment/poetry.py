"""
Poetry environment manager implementation.

This module provides a concrete implementation of the EnvironmentManager
protocol for projects managed with Poetry.
"""

from pathlib import Path
from typing import List

from pytest_analyzer.core.infrastructure.environment.base_manager import (
    BaseEnvironmentManager,
)


class PoetryManager(BaseEnvironmentManager):
    """
    Manages Python environments using Poetry.

    This class implements the EnvironmentManager protocol to interact with
    Poetry environments, allowing for command execution and environment detection.
    """

    NAME: str = "Poetry"

    def __init__(self, project_path: Path):
        """
        Initializes the PoetryManager.

        Args:
            project_path: The root path of the Poetry-managed project.
        """
        super().__init__(project_path)

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        """
        Detect if Poetry is used in the given project.

        Checks for the presence of a 'pyproject.toml' file containing
        a '[tool.poetry]' section.

        Args:
            project_path: The root path of the project to check.

        Returns:
            True if 'pyproject.toml' exists and contains '[tool.poetry]', False otherwise.
        """
        pyproject_file = project_path / "pyproject.toml"
        if not pyproject_file.is_file():
            return False
        try:
            content = pyproject_file.read_text(encoding="utf-8")
            return "[tool.poetry]" in content
        except IOError:
            return False

    def build_command(self, command: List[str]) -> List[str]:
        """
        Build a command list to be executed with Poetry.

        Prepends ["poetry", "run"] to the given command.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            A new list of strings representing the command ready for execution
            via 'poetry run'.
        """
        return ["poetry", "run"] + command
