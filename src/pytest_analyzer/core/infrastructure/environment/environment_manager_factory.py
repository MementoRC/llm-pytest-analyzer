"""
Factory for creating environment manager instances.

This module provides the EnvironmentManagerFactory class, responsible for
instantiating appropriate environment managers (e.g., Poetry, Pipenv, Hatch)
for a given Python project. It supports auto-detection based on project
configuration files and allows for explicit manager selection.
"""

from pathlib import Path
from typing import List, Optional, Type

from pytest_analyzer.core.environment.hatch import HatchManager
from pytest_analyzer.core.environment.pip_venv import (  # Assumed path and class name
    PipVenvManager,
)
from pytest_analyzer.core.environment.pipenv import PipenvManager
from pytest_analyzer.core.environment.pixi import PixiManager
from pytest_analyzer.core.environment.poetry import PoetryManager
from pytest_analyzer.core.environment.uv import UVManager
from pytest_analyzer.core.infrastructure.base_factory import BaseFactory
from pytest_analyzer.core.infrastructure.environment.base_manager import (
    BaseEnvironmentManager,
)
from pytest_analyzer.utils.config_types import (  # For type hinting __init__
    Settings,
)


class EnvironmentManagerFactory(BaseFactory):
    """
    Factory for creating and managing instances of environment managers.

    This factory can auto-detect the appropriate environment manager for a given
    project path or create a specific manager if its name is provided.
    It registers all known environment managers (Poetry, Pixi, Hatch, UV, Pipenv,
    and PipVenv) and uses a predefined order for auto-detection.
    PipVenvManager is used as a fallback if no specific manager is detected.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initializes the EnvironmentManagerFactory.

        Sets up the logger, initializes the registry for managers, defines the
        detection order, and registers all known environment managers.

        Args:
            settings: Optional configuration settings, passed to BaseFactory.
        """
        super().__init__(settings)

        # Define the order for auto-detection.
        # More specific or common managers should generally come first.
        self.ordered_manager_classes_for_detection: List[
            Type[BaseEnvironmentManager]
        ] = [
            PoetryManager,
            PixiManager,
            HatchManager,
            UVManager,
            PipenvManager,
            # PipVenvManager is handled as a fallback in create() if others are not detected.
            # It is registered but not part of this primary detection list by default,
            # as its detection logic might be too general.
        ]

        self._register_managers()

    def _register_managers(self) -> None:
        """
        Registers all known environment managers in the factory.

        Managers are registered using their 'NAME' attribute as the key.
        This allows for creating managers by name and for iterating through
        them for auto-detection. It assumes each manager class has a 'NAME'
        attribute and a 'detect(project_path: Path) -> bool' class method.
        """
        # Include all managers that should be available in the registry.
        all_manager_classes_to_register: List[Type[BaseEnvironmentManager]] = (
            self.ordered_manager_classes_for_detection + [PipVenvManager]
        )

        for manager_class in all_manager_classes_to_register:
            if not hasattr(manager_class, "NAME"):
                self.logger.warning(
                    f"Manager class {manager_class.__name__} is missing the NAME attribute "
                    f"and cannot be registered by name. Skipping."
                )
                continue

            self.logger.debug(f"Registering environment manager: {manager_class.NAME}")
            self.register(manager_class.NAME, manager_class)

    def create(
        self, project_path: Path, manager_name: Optional[str] = None
    ) -> BaseEnvironmentManager:
        """
        Creates an environment manager instance for the given project path.

        If 'manager_name' is provided, it attempts to create an instance of that
        specific manager using its registered name.

        If 'manager_name' is not provided, it auto-detects the manager by
        iterating through 'ordered_manager_classes_for_detection' and calling
        their 'detect' method. The first manager to positively detect the
        environment is chosen.

        If no specific manager is detected through this process, it defaults to
        creating a PipVenvManager instance as a fallback.

        Args:
            project_path: The Path object representing the root of the project.
            manager_name: Optional string name of the manager to create (e.g.,
                          "Poetry", "Pipenv"). If None, auto-detection is used.

        Returns:
            An initialized instance of a BaseEnvironmentManager subclass.

        Raises:
            KeyError: If 'manager_name' is specified but no such manager is
                      registered in the factory.
        """
        if manager_name:
            self.logger.info(
                f"Attempting to create specified manager '{manager_name}' for project: {project_path}"
            )
            try:
                manager_class = self.get_implementation(manager_name)
                return manager_class(project_path)
            except KeyError:
                self.logger.error(
                    f"Specified manager '{manager_name}' is not registered. "
                    f"Available registered managers: {list(self._registry.keys())}"
                )
                raise  # Re-raise the KeyError to signal failure

        self.logger.info(
            f"Auto-detecting environment manager for project: {project_path}"
        )
        for manager_class in self.ordered_manager_classes_for_detection:
            manager_display_name = getattr(
                manager_class, "NAME", manager_class.__name__
            )
            self.logger.debug(
                f"Checking for {manager_display_name} at {project_path}..."
            )
            if manager_class.detect(project_path):
                self.logger.info(
                    f"Detected {manager_display_name} for project: {project_path}"
                )
                # Always use the registered implementation if available (to allow for patching/mocking in tests)
                manager_name = getattr(manager_class, "NAME", None)
                if manager_name and manager_name in self._registry:
                    impl = self.get_implementation(manager_name)
                    return impl(project_path)
                else:
                    return manager_class(project_path)

        # Fallback to PipVenvManager if no other manager is detected
        pip_venv_display_name = getattr(
            PipVenvManager, "NAME", "PipVenvManager (default fallback)"
        )
        self.logger.info(
            f"No specific manager detected via ordered list for {project_path}. "
            f"Falling back to {pip_venv_display_name}."
        )
        # Use the registered implementation if available (to allow for patching/mocking in tests)
        try:
            fallback_manager_class = self.get_implementation(PipVenvManager.NAME)
            return fallback_manager_class(project_path)
        except (KeyError, AttributeError) as e:
            self.logger.warning(
                f"Could not retrieve '{pip_venv_display_name}' "
                f"from registry for fallback (Error: {e}). "
                f"Instantiating PipVenvManager directly as a hard fallback."
            )
            return PipVenvManager(project_path)
