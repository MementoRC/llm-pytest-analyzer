"""
Environment manager detection service.

This module provides a detector class to identify the active environment
manager in a given project path based on characteristic project files.
"""

from pathlib import Path
from typing import List, Optional, Type

# TODO: When actual manager implementations are available, import them instead of placeholders.
from .protocol import EnvironmentManager

# --- Placeholder Manager Implementations ---
# These are simplified versions for the detector to work with.
# They will be replaced by actual manager implementations in their own modules later.


class PlaceholderBaseManager(EnvironmentManager):
    """Base for placeholder managers to ensure protocol adherence."""

    NAME: str = "PlaceholderBase"

    def __init__(self, project_path: Path):
        """
        Initializes the placeholder manager.

        Args:
            project_path: The root path of the project.
        """
        self.project_path = project_path  # Store if needed by other methods

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        """Detects if this manager is active. Overridden by subclasses."""
        raise NotImplementedError(
            f"{cls.__name__} must implement the 'detect' class method."
        )

    def build_command(self, command: List[str]) -> List[str]:
        """Builds a command. Placeholder implementation."""
        return [self.NAME.lower(), "run"] + command

    def execute_command(self, command: List[str]) -> int:
        """Executes a command. Placeholder implementation."""
        return 0

    def activate(self) -> None:
        """Activates the environment. Placeholder implementation."""
        pass

    def deactivate(self) -> None:
        """Deactivates the environment. Placeholder implementation."""
        pass


class PixiManagerPlaceholder(PlaceholderBaseManager):
    """Placeholder for Pixi environment manager."""

    NAME = "Pixi"

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        return (project_path / "pixi.toml").is_file()


class PoetryManagerPlaceholder(PlaceholderBaseManager):
    """Placeholder for Poetry environment manager."""

    NAME = "Poetry"

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        pyproject_file = project_path / "pyproject.toml"
        if not pyproject_file.is_file():
            return False
        try:
            # TODO: Use a TOML parser for robustness instead of string searching.
            content = pyproject_file.read_text(encoding="utf-8")
            return "[tool.poetry]" in content
        except IOError:
            return False


class HatchManagerPlaceholder(PlaceholderBaseManager):
    """Placeholder for Hatch environment manager."""

    NAME = "Hatch"

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        pyproject_file = project_path / "pyproject.toml"
        if not pyproject_file.is_file():
            return False
        try:
            # TODO: Use a TOML parser for robustness instead of string searching.
            content = pyproject_file.read_text(encoding="utf-8")
            return "[tool.hatch]" in content or "[tool.hatch." in content
        except IOError:
            return False


class UVManagerPlaceholder(PlaceholderBaseManager):
    """Placeholder for UV environment manager."""

    NAME = "UV"

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        # PRD Rule: uv.lock file OR pyproject.toml with UV configuration
        # TODO: Add check for pyproject.toml [tool.uv] section.
        return (project_path / "uv.lock").is_file()


class PipenvManagerPlaceholder(PlaceholderBaseManager):
    """Placeholder for Pipenv environment manager."""

    NAME = "Pipenv"

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        return (project_path / "Pipfile").is_file() or (
            project_path / "Pipfile.lock"
        ).is_file()


class PipVenvManagerPlaceholder(PlaceholderBaseManager):
    """Placeholder for Pip+Venv environment manager."""

    NAME = "PipVenv"

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        # PRD Rule: requirements.txt with virtual environment
        # TODO: Detection of an active venv is more complex.
        # For now, presence of requirements.txt is a strong hint.
        return (project_path / "requirements.txt").is_file()


# Default order of managers to check. First one detected wins.
DEFAULT_MANAGERS: List[Type[EnvironmentManager]] = [
    PixiManagerPlaceholder,
    PoetryManagerPlaceholder,
    HatchManagerPlaceholder,
    UVManagerPlaceholder,
    PipenvManagerPlaceholder,
    PipVenvManagerPlaceholder,  # Often a fallback
]


# --- EnvironmentManagerDetector Class ---


class EnvironmentManagerDetector:
    """
    Detects the active environment manager for a given project.

    The detector iterates through a list of known environment manager classes,
    calling their `detect` method. The first manager to positively identify
    itself is considered the active one.
    """

    def __init__(
        self,
        project_path: Path,
        manager_classes: Optional[List[Type[EnvironmentManager]]] = None,
    ):
        """
        Initializes the detector.

        Args:
            project_path: The root path of the project to analyze.
            manager_classes: An optional list of environment manager classes
                             to use for detection, in order of priority.
                             If None, uses DEFAULT_MANAGERS.
        """
        self.project_path = project_path
        self.manager_classes = manager_classes or DEFAULT_MANAGERS
        self._detected_manager_type: Optional[Type[EnvironmentManager]] = None
        self._active_manager_instance: Optional[EnvironmentManager] = None
        self._detection_done: bool = False

    def detect_environment(self) -> Optional[Type[EnvironmentManager]]:
        """
        Detects the environment manager type based on project files.

        Iterates through the registered manager classes in order and returns
        the type of the first one that successfully detects its presence.
        Caches the result of the first detection.

        Returns:
            The class (type) of the detected environment manager, or None if no
            manager is detected.
        """
        if self._detection_done:
            return self._detected_manager_type

        for manager_class in self.manager_classes:
            try:
                if manager_class.detect(self.project_path):
                    self._detected_manager_type = manager_class
                    break  # Found the first manager
            except Exception:
                # TODO: Add proper logging for detection errors.
                # For now, silently continue to allow other detectors to run.
                pass

        self._detection_done = True
        return self._detected_manager_type

    def get_active_manager(self) -> Optional[EnvironmentManager]:
        """
        Gets an instance of the active environment manager.

        If a manager has already been detected and instantiated, returns the
        cached instance. Otherwise, performs detection and, if successful,
        instantiates the detected manager.

        Returns:
            An instance of the detected EnvironmentManager, or None if no
            manager is detected or if instantiation fails.
        """
        if self._active_manager_instance:
            return self._active_manager_instance

        detected_type = (
            self.detect_environment()
        )  # Uses cached type if already detected

        if detected_type:
            if self._detected_manager_type and isinstance(
                self._active_manager_instance, self._detected_manager_type
            ):
                # This case implies _active_manager_instance was already set for the detected_type
                return self._active_manager_instance

            try:
                # Assuming manager constructors are simple (no args or only project_path).
                # Placeholder managers have simple __init__ from PlaceholderBaseManager.
                # If real managers need project_path, their __init__ must accept it,
                # or they should be factories.
                # Pass project_path to the constructor.
                self._active_manager_instance = detected_type(
                    project_path=self.project_path
                )  # type: ignore
                return self._active_manager_instance
            except Exception:
                # TODO: Add proper logging for instantiation errors.
                self._active_manager_instance = None  # Ensure it's None on failure
                return None
        return None

    def clear_cache(self) -> None:
        """Clears the cached detected manager type and instance."""
        self._detected_manager_type = None
        self._active_manager_instance = None
        self._detection_done = False
