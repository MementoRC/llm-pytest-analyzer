"""
Base environment manager abstract class.

This module provides a base abstract class for all environment managers
to eliminate code duplication across Poetry, Pixi, Hatch, UV, and Pipenv managers.
"""

import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class BaseEnvironmentManager(ABC):
    """Base class for all environment managers to eliminate code duplication.

    This abstract base class provides common functionality shared across
    all environment manager implementations, reducing duplication and
    ensuring consistent behavior.
    """

    def __init__(self, project_path: Path):
        """Initialize the base environment manager.

        Args:
            project_path: The root path of the project managed by this environment manager.
        """
        self.project_path = project_path
        self.logger = logging.getLogger(self.__class__.__name__)

    def execute_command(self, command: List[str]) -> int:
        """Common implementation for executing commands in the project directory.

        This method provides a consistent way to execute commands across all
        environment managers, ensuring they run from the correct project directory
        with appropriate logging.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            The exit code of the executed command.
        """
        self.logger.debug(f"Executing command: {' '.join(command)}")
        return subprocess.call(command, cwd=self.project_path)

    def activate(self) -> None:
        """Default no-op implementation for environment activation.

        Most modern environment managers (Poetry, Pixi, Hatch, UV) handle
        activation implicitly through their run commands. Subclasses can
        override this method if explicit activation is required.
        """
        self.logger.debug("Environment activation not required")

    def deactivate(self) -> None:
        """Default no-op implementation for environment deactivation.

        Most modern environment managers handle deactivation automatically
        when their processes terminate. Subclasses can override this method
        if explicit deactivation is required.
        """
        self.logger.debug("Environment deactivation not required")

    @abstractmethod
    def build_command(self, base_command: List[str]) -> List[str]:
        """Manager-specific command building logic to be implemented by subclasses.

        This method must be implemented by each environment manager to define
        how base commands are transformed into environment-specific commands.

        Args:
            base_command: A list of strings representing the base command and its arguments.

        Returns:
            A new list of strings representing the command ready for execution
            within the specific environment manager context.
        """

    @classmethod
    @abstractmethod
    def detect(cls, project_path: Path) -> bool:
        """Detect if this environment manager is used in the given project.

        This method must be implemented by each environment manager to define
        how it detects its presence in a project (e.g., checking for specific
        configuration files).

        Args:
            project_path: The root path of the project to check.

        Returns:
            True if the environment manager is detected, False otherwise.
        """
