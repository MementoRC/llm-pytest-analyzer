"""
Tests for the EnvironmentManagerDetector.
"""

from pathlib import Path
from typing import List, Optional, Type
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.environment.detector import (
    PlaceholderBaseManager,  # Import base for isinstance checks if needed
)
from pytest_analyzer.core.environment.detector import (
    DEFAULT_MANAGERS,
    EnvironmentManagerDetector,
    HatchManagerPlaceholder,
    PipenvManagerPlaceholder,
    PipVenvManagerPlaceholder,
    PoetryManagerPlaceholder,
    UVManagerPlaceholder,
)
from pytest_analyzer.core.environment.pixi import PixiManager
from pytest_analyzer.core.environment.protocol import EnvironmentManager


# Helper to create mock file structures in a temporary directory
def create_project_files(
    tmp_path: Path,
    files_to_create: List[str],
    pyproject_content: Optional[str] = None,
):
    """Creates specified files in tmp_path. Handles pyproject.toml content."""
    for f_name in files_to_create:
        file_path = tmp_path / f_name
        file_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure parent dirs exist
        if f_name == "pyproject.toml" and pyproject_content:
            file_path.write_text(pyproject_content, encoding="utf-8")
        else:
            file_path.touch()


@pytest.fixture
def configured_managers() -> List[Type[EnvironmentManager]]:
    """Provides the default list of manager classes for testing."""
    return DEFAULT_MANAGERS


# A custom manager class for testing instantiation failure scenarios
class FailingManagerPlaceholder(PlaceholderBaseManager):
    """A manager designed to fail during instantiation for testing purposes."""

    NAME = "FailingManager"

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        # Detects based on a specific marker file for test control
        return (project_path / "fail_marker.txt").is_file()

    def __init__(self, project_path: Path):
        # This __init__ will be called by the detector upon instantiation
        super().__init__(project_path)  # Call base, passing project_path
        raise RuntimeError("Simulated instantiation failure for FailingManager")


# A helper manager class for testing error during detection
class MockErrorDetectManager(PlaceholderBaseManager):
    """A manager whose detect method can be patched to simulate errors."""

    NAME = "ErrorDetectManager"

    # __init__ is inherited from PlaceholderBaseManager, now accepting project_path

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        # This method will be patched in the test.
        # It needs a realistic signature for patching.
        return (project_path / "marker_for_error_detect_manager.txt").is_file()


class TestEnvironmentManagerDetector:
    """Tests for the EnvironmentManagerDetector class."""

    def test_init_with_default_managers(self, tmp_path: Path):
        """Test detector initialization with default manager classes."""
        detector = EnvironmentManagerDetector(project_path=tmp_path)
        assert detector.project_path == tmp_path
        assert detector.manager_classes == DEFAULT_MANAGERS
        assert detector._detected_manager_type is None
        assert detector._active_manager_instance is None
        assert not detector._detection_done

    def test_init_with_custom_managers(self, tmp_path: Path):
        """Test detector initialization with a custom list of manager classes."""
        mock_manager_class = MagicMock(spec=EnvironmentManager)
        # Ensure the mock has a 'detect' classmethod
        mock_manager_class.detect = classmethod(MagicMock(return_value=False))

        custom_managers: List[Type[EnvironmentManager]] = [mock_manager_class]  # type: ignore
        detector = EnvironmentManagerDetector(
            project_path=tmp_path, manager_classes=custom_managers
        )
        assert detector.manager_classes == custom_managers

    @pytest.mark.parametrize(
        "files_to_create, pyproject_content, expected_manager_type",
        [
            ([], None, None),  # No manager files
            (["pixi.toml"], None, PixiManager),
            (
                ["pyproject.toml"],
                '[tool.poetry]\nname = "test-project"',
                PoetryManagerPlaceholder,
            ),
            (
                ["pyproject.toml"],
                '[tool.hatch.version]\npath = "src/app/__about__.py"',
                HatchManagerPlaceholder,
            ),
            (["uv.lock"], None, UVManagerPlaceholder),
            (["Pipfile"], None, PipenvManagerPlaceholder),
            (["Pipfile.lock"], None, PipenvManagerPlaceholder),
            (["requirements.txt"], None, PipVenvManagerPlaceholder),
            # Priority: Pixi detected first if both pixi.toml and Pipfile exist
            (["pixi.toml", "Pipfile"], None, PixiManager),
            # Priority: Poetry before Hatch (based on DEFAULT_MANAGERS order)
            (
                ["pyproject.toml"],
                "[tool.poetry]\nname='p'\n[tool.hatch]\nversion='1'",
                PoetryManagerPlaceholder,
            ),
        ],
    )
    def test_detect_environment_scenarios(
        self,
        tmp_path: Path,
        configured_managers: List[Type[EnvironmentManager]],
        files_to_create: List[str],
        pyproject_content: Optional[str],
        expected_manager_type: Optional[Type[EnvironmentManager]],
    ):
        """Test various detection scenarios for detect_environment."""
        create_project_files(tmp_path, files_to_create, pyproject_content)
        detector = EnvironmentManagerDetector(
            project_path=tmp_path, manager_classes=configured_managers
        )

        detected_type = detector.detect_environment()

        assert detected_type == expected_manager_type
        assert detector._detection_done  # Should be true after detection attempt
        assert detector._detected_manager_type == expected_manager_type

    def test_detect_environment_caching(self, tmp_path: Path):
        """Test that detect_environment caches its result."""
        create_project_files(tmp_path, ["pixi.toml"])
        detector = EnvironmentManagerDetector(project_path=tmp_path)

        # Patch the 'detect' method of the first manager to monitor calls
        with patch.object(
            PixiManager, "detect", wraps=PixiManager.detect
        ) as mock_pixi_detect:
            mock_pixi_detect.return_value = True  # Ensure detection

            # First call to detect_environment
            manager_type1 = detector.detect_environment()
            assert manager_type1 == PixiManager
            mock_pixi_detect.assert_called_once_with(detector.project_path)

            # Second call to detect_environment
            manager_type2 = detector.detect_environment()
            assert manager_type2 == PixiManager
            # Assert that the underlying 'detect' method was NOT called again
            mock_pixi_detect.assert_called_once()

    def test_detect_environment_handles_error_in_one_manager(self, tmp_path: Path):
        """Test that detection continues if one manager's detect method fails."""
        create_project_files(tmp_path, ["Pipfile"])  # Pipenv should be detected

        # Order: Erroring manager first, then a working one
        custom_managers: List[Type[EnvironmentManager]] = [
            MockErrorDetectManager,
            PipenvManagerPlaceholder,
        ]
        detector = EnvironmentManagerDetector(
            project_path=tmp_path, manager_classes=custom_managers
        )

        # Patch the 'detect' method of MockErrorDetectManager to raise an exception
        with patch.object(
            MockErrorDetectManager,
            "detect",
            side_effect=Exception("Simulated detection error!"),
        ) as mock_error_detect_method:
            detected_type = detector.detect_environment()

            # Assert that detection proceeded and PipenvManager was found
            assert detected_type == PipenvManagerPlaceholder
            # Assert that the failing manager's detect method was called
            mock_error_detect_method.assert_called_once_with(detector.project_path)

    def test_get_active_manager_no_detection(
        self, tmp_path: Path, configured_managers: List[Type[EnvironmentManager]]
    ):
        """Test get_active_manager when no environment is detected."""
        # No relevant project files created
        detector = EnvironmentManagerDetector(
            project_path=tmp_path, manager_classes=configured_managers
        )
        manager_instance = detector.get_active_manager()
        assert manager_instance is None
        assert detector._active_manager_instance is None
        assert (
            detector._detected_manager_type is None
        )  # Should be None after failed detection
        assert detector._detection_done  # Detection attempt was made

    def test_get_active_manager_successful_detection_and_instantiation(
        self, tmp_path: Path
    ):
        """Test get_active_manager successfully detects and instantiates a manager."""
        create_project_files(tmp_path, ["pixi.toml"])
        detector = EnvironmentManagerDetector(
            project_path=tmp_path
        )  # Uses DEFAULT_MANAGERS

        manager_instance = detector.get_active_manager()

        assert manager_instance is not None
        assert isinstance(manager_instance, PixiManager)
        assert detector._active_manager_instance is manager_instance
        assert detector._detected_manager_type == PixiManager

    def test_get_active_manager_caches_instance(self, tmp_path: Path):
        """Test that get_active_manager caches the instantiated manager."""
        create_project_files(tmp_path, ["pixi.toml"])
        detector = EnvironmentManagerDetector(project_path=tmp_path)

        # Patch the __init__ of PixiManager to count instantiations
        # The path for patching is where PixiManager is defined.
        with patch(
            "pytest_analyzer.core.environment.pixi.PixiManager.__init__",
            autospec=True,  # Use autospec for better __init__ mocking
            return_value=None,  # __init__ should return None
        ) as mock_pixi_init:
            # First call to get_active_manager
            instance1 = detector.get_active_manager()
            assert isinstance(
                instance1, PixiManager
            )  # Type check still works due to how patch works
            mock_pixi_init.assert_called_once()  # Instantiated once

            # Second call to get_active_manager
            instance2 = detector.get_active_manager()
            assert instance2 is instance1  # Should be the exact same instance
            mock_pixi_init.assert_called_once()  # Still instantiated only once

    def test_get_active_manager_instantiation_failure(self, tmp_path: Path):
        """Test get_active_manager when manager instantiation fails."""
        create_project_files(
            tmp_path, ["fail_marker.txt"]
        )  # Triggers FailingManagerPlaceholder

        custom_managers = [FailingManagerPlaceholder, PixiManager]
        detector = EnvironmentManagerDetector(
            project_path=tmp_path, manager_classes=custom_managers
        )

        manager_instance = detector.get_active_manager()

        assert manager_instance is None
        assert detector._active_manager_instance is None
        # Detection of the type should have succeeded
        assert detector._detected_manager_type == FailingManagerPlaceholder
        assert detector._detection_done

    def test_clear_cache(self, tmp_path: Path):
        """Test that clear_cache resets detection state."""
        create_project_files(tmp_path, ["pixi.toml"])
        detector = EnvironmentManagerDetector(project_path=tmp_path)

        # Populate cache
        manager = detector.get_active_manager()
        assert manager is not None
        assert detector._detected_manager_type is not None
        assert detector._active_manager_instance is not None
        assert detector._detection_done

        detector.clear_cache()

        assert detector._detected_manager_type is None
        assert detector._active_manager_instance is None
        assert not detector._detection_done

        # Verify detection runs again after cache clear
        with patch.object(
            PixiManager, "detect", wraps=PixiManager.detect
        ) as mock_pixi_detect:
            mock_pixi_detect.return_value = True
            detector.get_active_manager()  # Should call detect again
            mock_pixi_detect.assert_called_once_with(detector.project_path)

    def test_multiple_managers_file_priority(self, tmp_path: Path):
        """Test priority when multiple manager files are present."""
        # Poetry is before Hatch in DEFAULT_MANAGERS
        create_project_files(
            tmp_path,
            ["pyproject.toml"],
            "[tool.poetry]\nname='p'\n\n[tool.hatch.version]\npath='src'",
        )
        detector_default_order = EnvironmentManagerDetector(
            project_path=tmp_path
        )  # Uses DEFAULT_MANAGERS

        detected_type = detector_default_order.detect_environment()
        assert detected_type == PoetryManagerPlaceholder

        manager_instance = detector_default_order.get_active_manager()
        assert isinstance(manager_instance, PoetryManagerPlaceholder)

        # Test with a custom reversed order of managers
        custom_managers_reversed = [HatchManagerPlaceholder, PoetryManagerPlaceholder]
        detector_reversed_order = EnvironmentManagerDetector(
            project_path=tmp_path, manager_classes=custom_managers_reversed
        )

        detected_type_reversed = detector_reversed_order.detect_environment()
        assert detected_type_reversed == HatchManagerPlaceholder

        manager_instance_reversed = detector_reversed_order.get_active_manager()
        assert isinstance(manager_instance_reversed, HatchManagerPlaceholder)

    @pytest.mark.parametrize(
        "manager_to_test, file_content_key",
        [
            (PoetryManagerPlaceholder, "[tool.poetry]"),
            (HatchManagerPlaceholder, "[tool.hatch]"),
        ],
    )
    def test_pyproject_toml_io_error_gracefully_handled(
        self,
        tmp_path: Path,
        manager_to_test: Type[EnvironmentManager],
        file_content_key: str,
    ):
        """Test that IOErrors during pyproject.toml parsing are handled."""
        pyproject_file = tmp_path / "pyproject.toml"
        # Create the file so that .is_file() passes
        pyproject_file.write_text(file_content_key)  # Valid content initially

        detector = EnvironmentManagerDetector(
            project_path=tmp_path, manager_classes=[manager_to_test]
        )

        # Patch read_text to simulate an IOError for this specific file
        with patch.object(
            Path, "read_text", side_effect=IOError("Simulated cannot read file")
        ):
            # This patch will affect the read_text call inside the manager's detect method
            detected_type = detector.detect_environment()
            assert detected_type is None  # Should not detect if file read fails
