"""
Environment manager detection service.

This module provides a detector class to identify the active environment
manager in a given project path based on characteristic project files.
"""

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Type

from .pixi import PixiManager

# TODO: When actual manager implementations are available, import them instead of placeholders.
from .protocol import EnvironmentManager

RELEVANT_PROJECT_FILES = [
    "pixi.toml",
    "pyproject.toml",
    "Pipfile",
    "Pipfile.lock",
    "requirements.txt",
    "uv.lock",
]


@dataclass
class CacheEntry:
    """Represents an entry in the EnvironmentManagerCache."""

    manager_instance: Optional[EnvironmentManager]
    timestamp: float = field(default_factory=time.monotonic)
    file_mtimes: Dict[str, float] = field(default_factory=dict)


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
    PixiManager,
    PoetryManagerPlaceholder,
    HatchManagerPlaceholder,
    UVManagerPlaceholder,
    PipenvManagerPlaceholder,
    PipVenvManagerPlaceholder,  # Often a fallback
]


# --- EnvironmentManagerCache Class ---


class EnvironmentManagerCache:
    """
    Caches detected EnvironmentManager instances for project paths.

    Features:
    - Time-based expiration (TTL) for cache entries.
    - File modification time tracking for cache invalidation.
    - LRU (Least Recently Used) eviction policy when cache size limit is reached.
    """

    def __init__(self, max_size: int = 128, ttl: int = 300):
        """
        Initializes the cache.

        Args:
            max_size: Maximum number of entries in the cache.
            ttl: Time-to-live for cache entries in seconds.
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[Path, CacheEntry] = OrderedDict()

    def _get_relevant_file_mtimes(self, project_path: Path) -> Dict[str, float]:
        """
        Gets the modification times of relevant project files.

        Args:
            project_path: The root path of the project.

        Returns:
            A dictionary mapping filenames to their modification timestamps.
        """
        mtimes: Dict[str, float] = {}
        for filename in RELEVANT_PROJECT_FILES:
            file_path = project_path / filename
            if file_path.is_file():
                try:
                    mtimes[filename] = file_path.stat().st_mtime
                except FileNotFoundError:
                    # File might have been deleted between is_file() and stat()
                    pass
        return mtimes

    def get(self, project_path: Path) -> Optional[CacheEntry]:
        """
        Retrieves a cache entry for the given project path if valid.

        Args:
            project_path: The project path to look up.

        Returns:
            The CacheEntry if found and valid, otherwise None.
        """
        if project_path not in self._cache:
            return None

        entry = self._cache[project_path]

        # Check TTL
        if time.monotonic() - entry.timestamp > self.ttl:
            del self._cache[project_path]
            return None

        # Check file modification times
        current_mtimes = self._get_relevant_file_mtimes(project_path)
        if current_mtimes != entry.file_mtimes:
            del self._cache[project_path]
            return None

        # Valid entry, move to end for LRU
        self._cache.move_to_end(project_path)
        return entry

    def set(
        self, project_path: Path, manager_instance: Optional[EnvironmentManager]
    ) -> None:
        """
        Adds or updates a cache entry for the given project path.

        Args:
            project_path: The project path.
            manager_instance: The EnvironmentManager instance to cache (can be None).
        """
        if project_path in self._cache:
            del self._cache[project_path]  # Remove to re-insert at the end
        elif len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # Evict LRU item

        current_mtimes = self._get_relevant_file_mtimes(project_path)
        entry = CacheEntry(
            manager_instance=manager_instance, file_mtimes=current_mtimes
        )
        self._cache[project_path] = entry

    def remove(self, project_path: Path) -> None:
        """
        Removes a specific entry from the cache.

        Args:
            project_path: The project path of the entry to remove.
        """
        if project_path in self._cache:
            del self._cache[project_path]

    def clear_all(self) -> None:
        """Clears all entries from the cache."""
        self._cache.clear()


_DEFAULT_DETECTOR_CACHE = EnvironmentManagerCache()


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
        cache: Optional[EnvironmentManagerCache] = None,  # Add cache parameter
    ):
        """
        Initializes the detector.

        Args:
            project_path: The root path of the project to analyze.
            manager_classes: An optional list of environment manager classes
                             to use for detection, in order of priority.
                             If None, uses DEFAULT_MANAGERS.
            cache: An optional instance of EnvironmentManagerCache.
                   If None, a default cache instance is created.
        """
        self.project_path = project_path
        self.manager_classes = manager_classes or DEFAULT_MANAGERS
        self.cache = cache or EnvironmentManagerCache()  # Initialize cache

    @classmethod
    def detect(
        cls,
        project_path: Path,
        manager_classes: Optional[List[Type[EnvironmentManager]]] = None,
        cache: Optional[EnvironmentManagerCache] = None,
    ) -> Optional[EnvironmentManager]:
        """
        Detects and returns an instance of the active environment manager for a given path.

        Results are cached based on TTL and project file modification times.
        If a manager type is detected but instantiation fails, this failure
        (represented as None) is also cached.

        Args:
            project_path: The root path of the project to analyze.
            manager_classes: An optional list of environment manager classes
                             to use for detection, in order of priority.
                             If None, uses DEFAULT_MANAGERS.
            cache: An optional instance of EnvironmentManagerCache.
                   If None, a global default cache instance is used.

        Returns:
            An instance of the detected EnvironmentManager, or None if no
            manager is detected, or if instantiation fails.
        """
        effective_cache = cache if cache is not None else _DEFAULT_DETECTOR_CACHE
        effective_manager_classes = manager_classes or DEFAULT_MANAGERS

        cached_entry = effective_cache.get(project_path)
        if cached_entry is not None:
            return cached_entry.manager_instance

        detected_manager_instance: Optional[EnvironmentManager] = None

        for manager_class in effective_manager_classes:
            try:
                if manager_class.detect(project_path):
                    try:
                        # Pass project_path to the constructor.
                        detected_manager_instance = manager_class(
                            project_path=project_path
                        )  # type: ignore
                        # Successfully instantiated
                    except Exception:
                        # TODO: Add proper logging for instantiation errors.
                        # Instantiation failed, result is None for this detection cycle.
                        detected_manager_instance = None
                    break  # Stop after first detected manager type (whether instantiated or not)
            except Exception:
                # TODO: Add proper logging for detection errors.
                # Silently continue to allow other detectors to run.
                pass

        effective_cache.set(project_path, detected_manager_instance)
        return detected_manager_instance

    def get_active_manager(self) -> Optional[EnvironmentManager]:
        """
        Gets an instance of the active environment manager for the project path
        configured in this detector instance.

        This method uses the `detect` class method, passing its own
        project_path, manager_classes, and cache instance.

        Returns:
            An instance of the detected EnvironmentManager, or None if no
            manager is detected or if instantiation fails.
        """
        # Calls the class method `detect` using the instance's specific configuration.
        return EnvironmentManagerDetector.detect(
            project_path=self.project_path,
            manager_classes=self.manager_classes,
            cache=self.cache,
        )

    def clear_cache(self) -> None:
        """Clears the cached detection result for this detector's project_path."""
        self.cache.remove(self.project_path)
