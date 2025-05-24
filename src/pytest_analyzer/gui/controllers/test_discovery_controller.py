import logging
from typing import TYPE_CHECKING, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from ...core.models.pytest_failure import PytestFailure
from .base_controller import BaseController

if TYPE_CHECKING:
    from ...core.analyzer_service import PytestAnalyzerService
    from ..background.task_manager import TaskManager

logger = logging.getLogger(__name__)


class TestDiscoveryController(BaseController):
    """Controller for discovering test files using synchronous filesystem scanning."""

    tests_discovered = pyqtSignal(list)  # Emits List[PytestFailure] (node IDs)
    discovery_task_started = pyqtSignal(str)  # Emits task_id (no longer emitted)
    discovery_started = pyqtSignal(str)  # Emits a message
    discovery_finished = pyqtSignal(str)  # Emits a message (success or failure)

    def __init__(
        self,
        analyzer_service: "PytestAnalyzerService",
        parent: Optional[QObject] = None,
        task_manager: Optional[
            "TaskManager"
        ] = None,  # Kept for BaseController compatibility if needed
    ):
        super().__init__(parent, task_manager=task_manager)  # Pass task_manager to BaseController
        self.analyzer_service = analyzer_service
        # _current_discovery_task_id is no longer needed for synchronous operation

        # Task manager signal connections are removed as tasks are no longer used here.

    @pyqtSlot()
    def request_discover_tests(self) -> None:
        """Initiates synchronous test file discovery using filesystem scan."""
        # Synchronous operation, no check for existing discovery needed.

        self.logger.info("Requesting synchronous test file discovery.")
        self.discovery_started.emit("Starting test file discovery...")

        project_root_path = self.analyzer_service.settings.project_root
        if not project_root_path:
            self.logger.error("Project root not set in settings. Cannot discover test files.")
            self.discovery_finished.emit("Discovery failed: Project root not configured.")
            QMessageBox.critical(
                None, "Discovery Error", "Project root is not configured in settings."
            )
            return

        # Common directories to exclude from test discovery
        # These are relative to the project_root_path
        excluded_dirs = [
            ".pixi/",
            ".venv/",
            "venv/",  # Common alternative for virtual envs
            ".env/",
            "env/",
            ".hatch/",
            ".git/",
            "__pycache__/",
            ".pytest_cache/",
            ".tox/",
            "node_modules/",
            "dist/",
            "build/",
            ".coverage/",
            ".mypy_cache/",
            ".ruff_cache/",
            "site-packages/",  # Often inside venvs but can be elsewhere
            "docs/",  # Typically not containing tests
            "examples/",  # Often not part of main test suite
        ]

        # Ensure project_root_path is a Path object.
        from pathlib import Path

        if not isinstance(project_root_path, Path):
            project_root_path = Path(project_root_path)

        discovered_items: List[PytestFailure] = []
        try:
            self.logger.info(f"Scanning for test files in {project_root_path}")

            # Using a set to avoid duplicates if rglob patterns overlap
            # or due to symlinks pointing within the same scanned area.
            test_file_paths = set()
            test_file_paths.update(project_root_path.rglob("test_*.py"))
            test_file_paths.update(project_root_path.rglob("*_test.py"))

            for file_path in test_file_paths:
                if not file_path.is_file():
                    continue

                relative_file_path_str = str(file_path.relative_to(project_root_path))

                # Check against excluded directories
                is_excluded = False
                for excluded_dir_pattern in excluded_dirs:
                    # Ensure pattern ends with a slash for directory matching,
                    # or handle exact file matches if patterns are specific.
                    # Current patterns like ".venv/" imply directory exclusion.
                    if relative_file_path_str.startswith(excluded_dir_pattern):
                        is_excluded = True
                        break

                if is_excluded:
                    self.logger.debug(f"Excluding file due to rule: {file_path}")
                    continue

                # Create a minimal PytestFailure object for the discovered file
                # Use the relative file path as the node ID to match pytest conventions
                failure_item = PytestFailure(
                    test_name=relative_file_path_str,  # Use relative file path as node ID
                    test_file=relative_file_path_str,
                    error_type="discovered_file",  # Indicates this is from discovery
                    error_message="",  # No error for discovered files
                    traceback="",  # No traceback for discovered files
                    line_number=None,
                )
                discovered_items.append(failure_item)

            self.logger.info(f"Discovered {len(discovered_items)} test files.")
            self.tests_discovered.emit(discovered_items)
            self.discovery_finished.emit(
                f"Test file discovery complete. Found {len(discovered_items)} files."
            )

        except Exception as e:
            self.logger.exception("Error during synchronous test file discovery:")
            self.discovery_finished.emit(f"Discovery failed: {e}")
            QMessageBox.critical(
                None, "Discovery Error", f"An error occurred during test file discovery:\n{e}"
            )

    # _handle_task_completion and _handle_task_failure are no longer needed
    # as the operation is synchronous and doesn't use the TaskManager directly.
