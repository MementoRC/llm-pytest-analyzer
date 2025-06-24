"""
Pixi environment manager implementation.

This module provides a concrete implementation of the EnvironmentManager
protocol for projects managed with Pixi.
"""

from pathlib import Path
from typing import List

from ..infrastructure.environment.base_manager import BaseEnvironmentManager


class PixiManager(BaseEnvironmentManager):
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
        super().__init__(project_path)

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
