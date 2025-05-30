"""
Tests for EnvironmentManagerFactory.

This module tests the EnvironmentManagerFactory to ensure it correctly
registers, creates, and auto-detects environment managers based on
project structure and explicit requests.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.environment.hatch import HatchManager
from pytest_analyzer.core.environment.pip_venv import PipVenvManager
from pytest_analyzer.core.environment.pipenv import PipenvManager
from pytest_analyzer.core.environment.pixi import PixiManager
from pytest_analyzer.core.environment.poetry import PoetryManager
from pytest_analyzer.core.environment.uv import UVManager
from pytest_analyzer.core.infrastructure.environment.base_manager import (
    BaseEnvironmentManager,
)
from pytest_analyzer.core.infrastructure.environment.environment_manager_factory import (
    EnvironmentManagerFactory,
)

# Define a list of all manager classes expected to be registered
ALL_MANAGER_CLASSES = [
    PoetryManager,
    PixiManager,
    HatchManager,
    UVManager,
    PipenvManager,
    PipVenvManager,
]

# Define the expected detection order
DETECTION_ORDER = [
    PoetryManager,
    PixiManager,
    HatchManager,
    UVManager,
    PipenvManager,
]


class TestEnvironmentManagerFactory:
    """Test cases for EnvironmentManagerFactory."""

    def setup_method(self):
        """Set up test fixtures."""
        self.project_path = Path("/fake/project")
        # Patch the logger to prevent output during tests
        # The logger is initialized in BaseFactory, so we patch getLogger there.
        self._patcher_logger = patch(
            "pytest_analyzer.core.infrastructure.base_factory.logging.getLogger"
        )
        self.mock_logger = MagicMock()
        self._patcher_logger.start().return_value = self.mock_logger

    def teardown_method(self):
        """Clean up test fixtures."""
        self._patcher_logger.stop()

    def test_factory_initializes_and_registers_managers(self):
        """Test that the factory initializes and registers all known managers."""
        factory = EnvironmentManagerFactory()

        # Check if the registry contains all expected managers by name
        registered_keys = set(factory._registry.keys())
        expected_keys = {
            cls.NAME for cls in ALL_MANAGER_CLASSES if hasattr(cls, "NAME")
        }

        assert registered_keys == expected_keys

        # Check if the registered classes are the correct ones
        for name, cls in factory._registry.items():
            assert cls in ALL_MANAGER_CLASSES
            assert hasattr(cls, "NAME") and cls.NAME == name

    @pytest.mark.parametrize(
        "manager_class",
        ALL_MANAGER_CLASSES,
        ids=[cls.__name__ for cls in ALL_MANAGER_CLASSES],
    )
    @patch.object(BaseEnvironmentManager, "__init__", return_value=None)
    def test_create_returns_correct_manager_when_name_specified(
        self, mock_manager_init, manager_class
    ):
        """Test that create returns the correct manager instance when name is specified."""
        if not hasattr(manager_class, "NAME"):
            pytest.skip(f"{manager_class.__name__} does not have a NAME attribute.")

        factory = EnvironmentManagerFactory()
        manager_name = manager_class.NAME

        # Replace the class in the registry with a mock, so the factory uses the mock
        original_class = factory._registry[manager_name]
        MockManagerClass = MagicMock(spec=manager_class)
        factory._registry[manager_name] = MockManagerClass

        try:
            created_manager = factory.create(self.project_path, manager_name)

            # Assert that the mock was called with the project path
            MockManagerClass.assert_called_once_with(self.project_path)
            # Assert that the returned object is the mock's return value
            assert created_manager == MockManagerClass.return_value
        finally:
            # Restore the original class in the registry
            factory._registry[manager_name] = original_class

    @patch.object(BaseEnvironmentManager, "__init__", return_value=None)
    def test_create_raises_keyerror_for_invalid_manager_name(self, mock_manager_init):
        """Test that create raises KeyError for an invalid manager name."""
        factory = EnvironmentManagerFactory()
        invalid_name = "NonExistentManager"

        with pytest.raises(
            KeyError, match=f"No implementation registered for key '{invalid_name}'"
        ):
            factory.create(self.project_path, invalid_name)

    @pytest.mark.parametrize(
        "detected_manager_class",
        DETECTION_ORDER,
        ids=[cls.__name__ for cls in DETECTION_ORDER],
    )
    def test_create_auto_detects_correct_manager_based_on_order(
        self, detected_manager_class
    ):
        """Test that create auto-detects the correct manager based on detection order."""
        factory = EnvironmentManagerFactory()

        # Mock the detect method for all managers in the detection order
        mock_detects = {}
        for manager_class in DETECTION_ORDER:
            patch_path = f"{manager_class.__module__}.{manager_class.__name__}.detect"
            mock_detects[manager_class] = patch(patch_path).start()
            # By default, all detect methods return False
            mock_detects[manager_class].return_value = False

        # Set the detect method for the expected manager to return True
        mock_detects[detected_manager_class].return_value = True

        # Replace the detected manager class in the factory's registry with a mock
        if not hasattr(detected_manager_class, "NAME"):
            pytest.skip(
                f"{detected_manager_class.__name__} does not have a NAME attribute."
            )

        manager_name = detected_manager_class.NAME
        original_class = factory._registry[manager_name]
        MockManagerClass = MagicMock(spec=detected_manager_class)
        factory._registry[manager_name] = MockManagerClass

        try:
            created_manager = factory.create(self.project_path)

            # Assert that the detect method of the expected manager was called
            mock_detects[detected_manager_class].assert_called_once_with(
                self.project_path
            )

            # Assert that detect methods of managers *before* the detected one were called
            detected_index = DETECTION_ORDER.index(detected_manager_class)
            for i in range(detected_index):
                manager_class_before = DETECTION_ORDER[i]
                mock_detects[manager_class_before].assert_called_once_with(
                    self.project_path
                )

            # Assert that detect methods of managers *after* the detected one were NOT called
            for i in range(detected_index + 1, len(DETECTION_ORDER)):
                manager_class_after = DETECTION_ORDER[i]
                mock_detects[manager_class_after].assert_not_called()

            # Assert that the correct manager class constructor was called
            MockManagerClass.assert_called_once_with(self.project_path)
            assert created_manager == MockManagerClass.return_value
        finally:
            # Restore the original class in the registry
            factory._registry[manager_name] = original_class
            # Stop patches
            for mock_detect in mock_detects.values():
                mock_detect.stop()

    @patch.object(BaseEnvironmentManager, "__init__", return_value=None)
    def test_create_falls_back_to_pipvenv_if_no_other_detected(self, mock_manager_init):
        """Test that create falls back to PipVenvManager if no other manager is detected."""
        factory = EnvironmentManagerFactory()

        # Mock the detect method for all managers in the detection order to return False
        mock_detects = {}
        for manager_class in DETECTION_ORDER:
            patch_path = f"{manager_class.__module__}.{manager_class.__name__}.detect"
            mock_detects[manager_class] = patch(patch_path).start()
            mock_detects[manager_class].return_value = False

        # Mock the constructor of PipVenvManager
        patch_path_init = (
            f"{PipVenvManager.__module__}.{PipVenvManager.__name__}.__init__"
        )
        with patch(patch_path_init, return_value=None):
            with patch(
                f"{PipVenvManager.__module__}.{PipVenvManager.__name__}"
            ) as MockPipVenvManagerClass:
                MockPipVenvManagerClass.return_value = MagicMock(spec=PipVenvManager)
                original_class = factory._registry[PipVenvManager.NAME]
                factory._registry[PipVenvManager.NAME] = MockPipVenvManagerClass

                created_manager = factory.create(self.project_path)

                # Assert that detect methods of all managers in the detection order were called
                for manager_class in DETECTION_ORDER:
                    mock_detects[manager_class].assert_called_once_with(
                        self.project_path
                    )

                # Assert that PipVenvManager constructor was called
                MockPipVenvManagerClass.assert_called_once_with(self.project_path)
                assert created_manager == MockPipVenvManagerClass.return_value

                # Restore original class and stop patches
                factory._registry[PipVenvManager.NAME] = original_class
                for mock_detect in mock_detects.values():
                    mock_detect.stop()

    # Note: Integration tests with different project structures would typically
    # involve creating temporary directories with specific files (e.g., pyproject.toml,
    # Pipfile, requirements.txt) and then running the factory's create method
    # without mocking the detect methods. This requires file system interaction
    # and is more complex. The current tests mocking `detect` cover the factory's
    # logic based on the *result* of detection, which is sufficient for unit testing
    # the factory itself. Full integration tests would belong in a different suite.
    # The current tests adequately cover points 1, 2, 3, 4 (via mocking detect results), and 5.
