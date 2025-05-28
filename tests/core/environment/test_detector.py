"""
Tests for the EnvironmentManagerDetector.
"""

import time
from pathlib import Path
from typing import List, Optional, Type
from unittest.mock import MagicMock, patch

import pytest

from pytest_analyzer.core.environment.detector import (
    PlaceholderBaseManager,  # Import base for isinstance checks if needed
)
from pytest_analyzer.core.environment.detector import (
    DEFAULT_MANAGERS,
    RELEVANT_PROJECT_FILES,
    EnvironmentManagerCache,
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


# --- Tests for EnvironmentManagerCache ---


@pytest.fixture
def cache_fixture(tmp_path: Path) -> EnvironmentManagerCache:
    """Provides a clean EnvironmentManagerCache instance for each test."""
    # Using small max_size and ttl for easier testing of eviction and expiration
    return EnvironmentManagerCache(max_size=3, ttl=0.1)


@pytest.fixture
def mock_manager_instance() -> MagicMock:
    """Provides a mock EnvironmentManager instance."""
    return MagicMock(spec=EnvironmentManager)


class TestEnvironmentManagerCache:
    """Tests for the EnvironmentManagerCache class."""

    def test_cache_miss_and_set(
        self,
        cache_fixture: EnvironmentManagerCache,
        tmp_path: Path,
        mock_manager_instance: MagicMock,
    ):
        """Test cache miss, then set, then hit."""
        assert cache_fixture.get(tmp_path) is None  # Cache miss

        cache_fixture.set(tmp_path, mock_manager_instance)
        entry = cache_fixture.get(tmp_path)
        assert entry is not None
        assert entry.manager_instance == mock_manager_instance

    def test_ttl_expiration(
        self,
        cache_fixture: EnvironmentManagerCache,
        tmp_path: Path,
        mock_manager_instance: MagicMock,
    ):
        """Test that cache entries expire after TTL."""
        cache_fixture.set(tmp_path, mock_manager_instance)
        assert cache_fixture.get(tmp_path) is not None  # Should be a hit

        time.sleep(cache_fixture.ttl + 0.1)  # Wait for TTL to expire
        assert cache_fixture.get(tmp_path) is None  # Should be a miss due to TTL

    def test_mtime_invalidation_file_changed(
        self,
        cache_fixture: EnvironmentManagerCache,
        tmp_path: Path,
        mock_manager_instance: MagicMock,
    ):
        """Test cache invalidation if a relevant file's mtime changes."""
        # Create a relevant file (e.g., one from RELEVANT_PROJECT_FILES)
        relevant_file = tmp_path / RELEVANT_PROJECT_FILES[0]
        relevant_file.touch()

        cache_fixture.set(tmp_path, mock_manager_instance)
        assert cache_fixture.get(tmp_path) is not None  # Initial hit

        # Modify the file
        time.sleep(0.01)  # Ensure mtime is different
        relevant_file.write_text("new content")

        assert (
            cache_fixture.get(tmp_path) is None
        )  # Should be a miss due to mtime change

    def test_mtime_invalidation_file_added(
        self,
        cache_fixture: EnvironmentManagerCache,
        tmp_path: Path,
        mock_manager_instance: MagicMock,
    ):
        """Test cache invalidation if a new relevant file is added."""
        # Initially, no relevant files
        cache_fixture.set(tmp_path, mock_manager_instance)
        assert cache_fixture.get(tmp_path) is not None  # Initial hit

        # Add a new relevant file
        new_relevant_file = tmp_path / RELEVANT_PROJECT_FILES[0]
        new_relevant_file.touch()

        assert cache_fixture.get(tmp_path) is None  # Should be a miss

    def test_mtime_invalidation_file_removed(
        self,
        cache_fixture: EnvironmentManagerCache,
        tmp_path: Path,
        mock_manager_instance: MagicMock,
    ):
        """Test cache invalidation if a relevant file is removed."""
        relevant_file = tmp_path / RELEVANT_PROJECT_FILES[0]
        relevant_file.touch()

        cache_fixture.set(tmp_path, mock_manager_instance)
        assert cache_fixture.get(tmp_path) is not None  # Initial hit

        relevant_file.unlink()  # Remove the file
        assert cache_fixture.get(tmp_path) is None  # Should be a miss

    def test_lru_eviction(
        self,
        cache_fixture: EnvironmentManagerCache,
        tmp_path: Path,
        mock_manager_instance: MagicMock,
    ):
        """Test LRU eviction policy when cache exceeds max_size."""
        # cache_fixture.max_size is 3
        path1 = tmp_path / "proj1"
        path2 = tmp_path / "proj2"
        path3 = tmp_path / "proj3"
        path4 = tmp_path / "proj4"

        paths = [path1, path2, path3, path4]
        for p in paths:
            p.mkdir(exist_ok=True)

        # Fill the cache
        cache_fixture.set(path1, mock_manager_instance)  # LRU
        time.sleep(
            0.01
        )  # Ensure different timestamps for entries if needed by underlying dict
        cache_fixture.set(path2, mock_manager_instance)
        time.sleep(0.01)
        cache_fixture.set(path3, mock_manager_instance)  # MRU

        # Add one more, should evict path1 (LRU)
        cache_fixture.set(path4, mock_manager_instance)

        assert cache_fixture.get(path1) is None  # path1 should be evicted
        assert cache_fixture.get(path2) is not None
        assert cache_fixture.get(path3) is not None
        assert cache_fixture.get(path4) is not None

        # Access path2 to make it MRU
        cache_fixture.get(path2)
        path5 = tmp_path / "proj5"
        path5.mkdir(exist_ok=True)
        cache_fixture.set(path5, mock_manager_instance)  # Should evict path3

        assert cache_fixture.get(path3) is None  # path3 should be evicted
        assert (
            cache_fixture.get(path2) is not None
        )  # path2 was accessed, now MRU among old ones
        assert cache_fixture.get(path4) is not None
        assert cache_fixture.get(path5) is not None

    def test_set_updates_existing_entry_and_moves_to_mru(
        self, cache_fixture: EnvironmentManagerCache, tmp_path: Path
    ):
        """Test that set() updates an existing entry and marks it as MRU."""
        # cache_fixture.max_size is 3
        path1 = tmp_path / "proj1"
        path2 = tmp_path / "proj2"
        path3 = tmp_path / "proj3"

        mock_manager1 = MagicMock(spec=EnvironmentManager, name="mgr1")
        mock_manager2 = MagicMock(spec=EnvironmentManager, name="mgr2")

        for p in [path1, path2, path3]:
            p.mkdir(exist_ok=True)

        cache_fixture.set(path1, mock_manager1)  # LRU
        time.sleep(0.01)
        cache_fixture.set(path2, mock_manager1)
        time.sleep(0.01)
        cache_fixture.set(path3, mock_manager1)  # MRU

        # Update path1, it should become MRU
        cache_fixture.set(path1, mock_manager2)
        entry1 = cache_fixture.get(path1)
        assert entry1 is not None
        assert entry1.manager_instance == mock_manager2  # Check updated instance

        # Now, if we add another item, path2 should be evicted (was oldest)
        path4 = tmp_path / "proj4"
        path4.mkdir(exist_ok=True)
        cache_fixture.set(path4, mock_manager1)

        assert cache_fixture.get(path2) is None  # path2 should be evicted
        assert cache_fixture.get(path1) is not None  # path1 was updated, became MRU
        assert cache_fixture.get(path3) is not None
        assert cache_fixture.get(path4) is not None

    def test_remove_entry(
        self,
        cache_fixture: EnvironmentManagerCache,
        tmp_path: Path,
        mock_manager_instance: MagicMock,
    ):
        """Test removing a specific entry from the cache."""
        cache_fixture.set(tmp_path, mock_manager_instance)
        assert cache_fixture.get(tmp_path) is not None

        cache_fixture.remove(tmp_path)
        assert cache_fixture.get(tmp_path) is None

        # Test removing non-existent entry (should not fail)
        cache_fixture.remove(tmp_path / "non_existent")

    def test_clear_all_cache(
        self,
        cache_fixture: EnvironmentManagerCache,
        tmp_path: Path,
        mock_manager_instance: MagicMock,
    ):
        """Test clearing all entries from the cache."""
        path1 = tmp_path / "proj1"
        path2 = tmp_path / "proj2"
        path1.mkdir()
        path2.mkdir()

        cache_fixture.set(path1, mock_manager_instance)
        cache_fixture.set(path2, mock_manager_instance)
        assert cache_fixture.get(path1) is not None
        assert cache_fixture.get(path2) is not None

        cache_fixture.clear_all()
        assert cache_fixture.get(path1) is None
        assert cache_fixture.get(path2) is None
        assert len(cache_fixture._cache) == 0


# --- Tests for EnvironmentManagerDetector ---


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
        # Internal state attributes _detected_manager_type, _active_manager_instance,
        # and _detection_done have been removed.
        # Assert that an instance cache is created by default
        assert isinstance(detector.cache, EnvironmentManagerCache)

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

    def test_init_with_custom_cache(self, tmp_path: Path):
        """Test detector initialization with a custom cache instance."""
        my_cache = EnvironmentManagerCache()
        detector = EnvironmentManagerDetector(project_path=tmp_path, cache=my_cache)
        assert detector.cache is my_cache

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
    def test_class_detect_scenarios(  # Renamed and adapted
        self,
        tmp_path: Path,
        configured_managers: List[Type[EnvironmentManager]],
        files_to_create: List[str],
        pyproject_content: Optional[str],
        expected_manager_type: Optional[Type[EnvironmentManager]],
        cache_fixture: EnvironmentManagerCache,  # Use a clean cache for each run
    ):
        """Test various detection scenarios for EnvironmentManagerDetector.detect class method."""
        create_project_files(tmp_path, files_to_create, pyproject_content)

        # Test with a provided cache
        detected_manager_instance_with_cache = EnvironmentManagerDetector.detect(
            project_path=tmp_path,
            manager_classes=configured_managers,
            cache=cache_fixture,
        )

        if expected_manager_type is None:
            assert detected_manager_instance_with_cache is None
        else:
            assert isinstance(
                detected_manager_instance_with_cache, expected_manager_type
            )

        # Verify caching occurred in the provided cache
        cached_entry = cache_fixture.get(tmp_path)
        assert cached_entry is not None
        if expected_manager_type is None:
            assert cached_entry.manager_instance is None
        else:
            assert isinstance(cached_entry.manager_instance, expected_manager_type)

        # Test with cache=None (should use global default cache)
        # Clear the global cache first for a clean test run, or use a separate project path
        # For simplicity, let's assume global cache might be affected by other tests if not careful.
        # A more robust way would be to patch _DEFAULT_DETECTOR_CACHE for this specific test.
        with patch(
            "pytest_analyzer.core.environment.detector._DEFAULT_DETECTOR_CACHE",
            EnvironmentManagerCache(),  # Use a fresh default cache for this call
        ) as mock_default_cache:
            # Create a new project path to avoid collision with previous cache_fixture use on tmp_path
            project_path_for_default_cache_test = tmp_path / "proj_default_cache"
            project_path_for_default_cache_test.mkdir(exist_ok=True)
            # Re-create files in this new path if needed, or assume files_to_create are simple like "pixi.toml"
            # For this example, let's re-create.
            create_project_files(
                project_path_for_default_cache_test, files_to_create, pyproject_content
            )

            detected_manager_instance_no_cache = EnvironmentManagerDetector.detect(
                project_path=project_path_for_default_cache_test,  # Use distinct path
                manager_classes=configured_managers,
                cache=None,  # Test default cache usage
            )
            if expected_manager_type is None:
                assert detected_manager_instance_no_cache is None
            else:
                assert isinstance(
                    detected_manager_instance_no_cache, expected_manager_type
                )

            # Verify caching occurred in the (mocked) default cache
            assert (
                mock_default_cache.get(project_path_for_default_cache_test) is not None
            )

    def test_class_detect_uses_cache(
        self, tmp_path: Path, cache_fixture: EnvironmentManagerCache
    ):
        """Test that EnvironmentManagerDetector.detect uses the cache."""
        create_project_files(tmp_path, ["pixi.toml"])

        # First call, should populate cache
        manager1 = EnvironmentManagerDetector.detect(
            project_path=tmp_path, manager_classes=[PixiManager], cache=cache_fixture
        )
        assert isinstance(manager1, PixiManager)

        # To verify caching, we can mock the manager's detect or __init__
        # to ensure it's not called again for the same project_path.
        with (
            patch.object(
                PixiManager, "detect", wraps=PixiManager.detect
            ) as mock_pixi_detect_method,
            patch.object(
                PixiManager,
                "__init__",
                side_effect=lambda project_path: PixiManager(project_path),
            ) as mock_pixi_init,
        ):
            # The side_effect for __init__ ensures it can still be called if needed but allows counting/asserting.
            # Re-assigning the original __init__ or a simple lambda that calls it is safer than `wraps` for __init__.

            manager2 = EnvironmentManagerDetector.detect(
                project_path=tmp_path,
                manager_classes=[PixiManager],
                cache=cache_fixture,
            )
            assert isinstance(manager2, PixiManager)
            assert manager2 is manager1  # Should be the same instance from cache

            mock_pixi_detect_method.assert_not_called()
            mock_pixi_init.assert_not_called()

    def test_class_detect_handles_error_in_one_manager(
        self, tmp_path: Path, cache_fixture: EnvironmentManagerCache
    ):
        """Test that class detect continues if one manager's detect method fails."""
        create_project_files(tmp_path, ["Pipfile"])  # Pipenv should be detected

        # Order: Erroring manager first, then a working one
        custom_managers: List[Type[EnvironmentManager]] = [
            MockErrorDetectManager,
            PipenvManagerPlaceholder,
        ]
        # Patch the 'detect' method of MockErrorDetectManager to raise an exception
        with patch.object(
            MockErrorDetectManager,
            "detect",
            side_effect=Exception("Simulated detection error!"),
        ) as mock_error_detect_method:
            detected_manager = EnvironmentManagerDetector.detect(
                project_path=tmp_path,
                manager_classes=custom_managers,
                cache=cache_fixture,
            )

            # Assert that detection proceeded and PipenvManager was found
            assert isinstance(detected_manager, PipenvManagerPlaceholder)
            # Assert that the failing manager's detect method was called
            mock_error_detect_method.assert_called_once_with(
                tmp_path
            )  # project_path is tmp_path

    def test_get_active_manager_no_detection(
        self, tmp_path: Path, configured_managers: List[Type[EnvironmentManager]]
    ):
        """Test get_active_manager when no environment is detected."""
        detector = EnvironmentManagerDetector(
            project_path=tmp_path, manager_classes=configured_managers
        )
        manager_instance = detector.get_active_manager()
        assert manager_instance is None
        # Verify that the instance's cache was populated with None
        cached_entry = detector.cache.get(tmp_path)
        assert cached_entry is not None
        assert cached_entry.manager_instance is None

    def test_get_active_manager_successful_detection_and_instantiation(
        self, tmp_path: Path
    ):
        """Test get_active_manager successfully detects and instantiates a manager."""
        create_project_files(tmp_path, ["pixi.toml"])
        detector = EnvironmentManagerDetector(project_path=tmp_path)

        manager_instance = detector.get_active_manager()

        assert manager_instance is not None
        assert isinstance(manager_instance, PixiManager)
        # Verify that the instance's cache was populated
        cached_entry = detector.cache.get(tmp_path)
        assert cached_entry is not None
        assert cached_entry.manager_instance is manager_instance

    def test_get_active_manager_uses_instance_cache(self, tmp_path: Path):
        """Test that get_active_manager uses its configured instance cache."""
        create_project_files(tmp_path, ["pixi.toml"])

        # Use a specific cache instance for the detector
        instance_cache = EnvironmentManagerCache()
        detector = EnvironmentManagerDetector(
            project_path=tmp_path, cache=instance_cache
        )

        # Patch the class method `detect` to monitor calls and behavior with cache
        # We want to ensure get_active_manager passes its own cache to the class method.
        with patch.object(
            EnvironmentManagerDetector,
            "detect",
            wraps=EnvironmentManagerDetector.detect,
        ) as mock_class_detect:
            # First call to get_active_manager
            instance1 = detector.get_active_manager()
            assert isinstance(instance1, PixiManager)
            # Check that class detect was called with the instance's cache
            mock_class_detect.assert_called_once_with(
                project_path=tmp_path,
                manager_classes=detector.manager_classes,
                cache=instance_cache,
            )

            # Ensure the instance_cache was populated
            assert instance_cache.get(tmp_path) is not None
            assert instance_cache.get(tmp_path).manager_instance is instance1

            mock_class_detect.reset_mock()

            # Second call to get_active_manager
            instance2 = detector.get_active_manager()
            assert instance2 is instance1  # Should be the same instance from cache

            mock_class_detect.assert_called_once_with(
                project_path=tmp_path,
                manager_classes=detector.manager_classes,
                cache=instance_cache,
            )
            # To further verify no re-detection by the class method `detect` itself,
            # (i.e., it found the result in `instance_cache` passed to it),
            # we patch deeper, into PixiManager's detect/init.
            with (
                patch.object(PixiManager, "detect") as deeper_manager_detect,
                patch.object(PixiManager, "__init__") as deeper_manager_init,
            ):
                # Call get_active_manager again. mock_class_detect will be called.
                # The wrapped class detect method will then check instance_cache.
                # Since it's populated, deeper_manager_detect/init should not be called.
                detector.get_active_manager()
                deeper_manager_detect.assert_not_called()
                deeper_manager_init.assert_not_called()

    def test_get_active_manager_instantiation_failure_is_cached(self, tmp_path: Path):
        """Test get_active_manager when manager instantiation fails; None should be cached."""
        create_project_files(tmp_path, ["fail_marker.txt"])

        custom_managers = [FailingManagerPlaceholder, PixiManager]
        detector = EnvironmentManagerDetector(
            project_path=tmp_path, manager_classes=custom_managers
        )

        manager_instance = detector.get_active_manager()
        assert manager_instance is None

        # Verify that None is cached in the instance's cache
        cached_entry = detector.cache.get(tmp_path)
        assert cached_entry is not None
        assert cached_entry.manager_instance is None

        # Call again, should get None from cache without re-triggering FailingManager's __init__
        # Patch FailingManagerPlaceholder.__init__ to ensure it's not called again.
        with patch.object(
            FailingManagerPlaceholder,
            "__init__",
            side_effect=RuntimeError("Should not be called"),
        ) as mock_failing_init:
            manager_instance_cached = detector.get_active_manager()
            assert manager_instance_cached is None
            mock_failing_init.assert_not_called()

    def test_clear_cache_on_detector_instance(self, tmp_path: Path):
        """Test that detector.clear_cache() clears the instance's cache for its project_path."""
        create_project_files(tmp_path, ["pixi.toml"])
        detector = EnvironmentManagerDetector(project_path=tmp_path)

        # Populate cache
        manager = detector.get_active_manager()
        assert manager is not None
        assert detector.cache.get(tmp_path) is not None  # Instance cache has entry

        detector.clear_cache()  # This calls self.cache.remove(self.project_path)

        assert (
            detector.cache.get(tmp_path) is None
        )  # Entry for this project_path removed

        # Verify detection runs again and repopulates the cache
        manager2 = detector.get_active_manager()
        assert isinstance(manager2, PixiManager), (
            "Manager instance after cache clear is not PixiManager"
        )

        # Check that the cache is repopulated with the new manager instance
        cached_entry2 = detector.cache.get(tmp_path)
        assert cached_entry2 is not None, (
            "Cache is empty after second get_active_manager call"
        )
        assert cached_entry2.manager_instance is manager2, (
            "Cache not repopulated with the new manager instance"
        )

        # Ensure a new instance was created, indicating re-detection and re-instantiation
        assert manager2 is not manager, (
            "A new manager instance was not created after cache clear"
        )

    def test_multiple_managers_file_priority_with_get_active_manager(
        self, tmp_path: Path
    ):
        """Test priority with get_active_manager when multiple manager files are present."""
        create_project_files(
            tmp_path,
            ["pyproject.toml"],
            "[tool.poetry]\nname='p'\n\n[tool.hatch.version]\npath='src'",
        )

        # Default order: Poetry before Hatch
        detector_default_order = EnvironmentManagerDetector(project_path=tmp_path)
        manager_instance_default = detector_default_order.get_active_manager()
        assert isinstance(manager_instance_default, PoetryManagerPlaceholder)

        # Custom reversed order
        custom_managers_reversed = [HatchManagerPlaceholder, PoetryManagerPlaceholder]
        detector_reversed_order = EnvironmentManagerDetector(
            project_path=tmp_path, manager_classes=custom_managers_reversed
        )
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
        pyproject_file.write_text(file_content_key)

        # Use a clean cache for this test
        cache = EnvironmentManagerCache()

        # Verify the file exists first (sanity check)
        assert pyproject_file.is_file(), "pyproject.toml should exist for this test"

        # Now test the actual implementation handles IOError properly
        # Patch read_text to simulate an IOError during file reading
        original_read_text = Path.read_text

        def read_text_with_error(self, *args, **kwargs):
            if self.name == "pyproject.toml":
                raise IOError("Simulated cannot read file")
            return original_read_text(self, *args, **kwargs)

        with patch.object(Path, "read_text", side_effect=read_text_with_error):
            detected_manager = EnvironmentManagerDetector.detect(
                project_path=tmp_path, manager_classes=[manager_to_test], cache=cache
            )
            assert detected_manager is None  # Should not detect if file read fails

            # The important part is that the detection gracefully handles the IOError
            # We don't need to verify specific call patterns, just that it returns None
