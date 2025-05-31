"""
Protocol definition for environment managers.

This module defines the core protocol interface for environment managers,
which are responsible for managing Python virtual environments or other
project-specific execution contexts.
"""

from pathlib import Path
from typing import List, Protocol, runtime_checkable


@runtime_checkable
class EnvironmentManager(Protocol):
    """
    Protocol for managing Python environments.

    Implementations of this protocol are responsible for detecting,
    activating, deactivating, and executing commands within specific
    Python environments (e.g., venv, conda).
    """

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        """
        Detect if this environment manager is used in the given project.

        Args:
            project_path: The root path of the project to check.

        Returns:
            True if the environment manager is detected, False otherwise.
        """
        ...

    def build_command(self, command: List[str]) -> List[str]:
        """
        Build a command list to be executed within the managed environment.

        This method should prepend any necessary activation or environment-specific
        prefixes to the given command.

        Args:
            command: A list of strings representing the command and its arguments.

        Returns:
            A new list of strings representing the command ready for execution
            within the environment.
        """
        ...

    def execute_command(self, command: List[str]) -> int:
        """
        Execute a command within the managed environment.

        Args:
            command: A list of strings representing the command and its arguments.
                     This command should typically be processed by `build_command` first,
                     or be a command that inherently runs in the correct context if
                     the environment is already active.

        Returns:
            The exit code of the executed command.
        """
        ...

    def activate(self) -> None:
        """
        Activate the managed environment.

        This might involve setting environment variables or modifying the PATH.
        The specifics depend on the environment manager implementation.
        """
        ...

    def deactivate(self) -> None:
        """
        Deactivate the managed environment.

        This should revert any changes made by `activate`.
        """
        ...
