"""
Hatch environment manager implementation.

This module provides a concrete implementation of the EnvironmentManager
protocol for projects managed with Hatch.
"""

from pathlib import Path
from typing import List

from ..infrastructure.environment.base_manager import BaseEnvironmentManager


class HatchManager(BaseEnvironmentManager):
    """
    Manages Python environments using Hatch.

    This class implements the EnvironmentManager protocol to interact with
    Hatch environments, allowing for command execution and environment detection.
    """

    NAME: str = "Hatch"

    def __init__(self, project_path: Path):
        """
        Initializes the HatchManager.

        Args:
            project_path: The root path of the Hatch-managed project.
        """
        super().__init__(project_path)

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        """
        Detect if Hatch is used in the given project.

        Checks for 'pyproject.toml' containing '[tool.hatch]' or '[tool.hatch.]'.

        Args:
            project_path: The root path of the project to check.

        Returns:
            True if detected, False otherwise.
        """
        pyproject_file = project_path / "pyproject.toml"
        if not pyproject_file.is_file():
            return False
        try:
            content = pyproject_file.read_text(encoding="utf-8")
            return "[tool.hatch]" in content or "[tool.hatch." in content
        except IOError:
            return False

    def build_command(self, command: List[str]) -> List[str]:
        """
        Build a command list to be executed with Hatch.

        Prepends ["hatch", "run"] to the given command.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            A new list of strings representing the command ready for execution
            via 'hatch run'.
        """
        return ["hatch", "run"] + command
