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

        from pathlib import Path

        if not isinstance(project_root_path, Path):
            project_root_path_obj = Path(project_root_path)
        else:
            project_root_path_obj = project_root_path

        discovered_items: List[PytestFailure] = []
        try:
            self.logger.info(
                f"Starting synchronous test file discovery in '{project_root_path_obj}'"
            )

            all_python_files = project_root_path_obj.rglob("*.py")

            for file_path in all_python_files:
                if not file_path.is_file():
                    self.logger.debug(f"Skipping non-file item: {file_path}")
                    continue

                relative_path = file_path.relative_to(project_root_path_obj)
                relative_path_str = str(relative_path)
                path_parts = relative_path.parts
                lower_path_parts = tuple(part.lower() for part in path_parts)
                file_name = file_path.name
                file_name_lower = file_name.lower()

                # --- Early Filename Exclusion ---
                excluded_filenames = {
                    "__init__.py",
                    "conftest.py",
                    "fixtures.py",
                    "utils.py",  # Common utility file names in test dirs
                    "setup.py",  # Setup script, not a test
                }
                if file_name_lower in excluded_filenames:
                    self.logger.debug(
                        f"Skipping '{relative_path_str}' due to explicitly excluded filename."
                    )
                    continue

                # --- Path-based Exclusion Logic ---
                is_excluded = False

                # 1. Check for keywords in path components (e.g., .pixi, site-packages, envs)
                exclusion_keywords_in_parts = {
                    ".pixi",
                    "site-packages",
                    "envs",
                    ".git",
                    ".venv",
                    "venv",
                    ".env",
                    ".hatch",
                    "__pycache__",
                    ".pytest_cache",
                    ".tox",
                    "node_modules",
                    "dist",
                    "build",
                    ".coverage",
                    ".mypy_cache",
                    ".ruff_cache",
                }
                # Check directory parts (all parts except the filename itself)
                for i, dir_part_content in enumerate(path_parts[:-1]):
                    # dir_part_lower for matching, dir_part_content for logging
                    dir_part_lower = lower_path_parts[i]
                    for keyword in exclusion_keywords_in_parts:
                        if keyword in dir_part_lower:
                            self.logger.debug(
                                f"Excluding '{relative_path_str}' due to path component "
                                f"'{dir_part_content}' containing keyword '{keyword}'."
                            )
                            is_excluded = True
                            break
                    if is_excluded:
                        break
                if is_excluded:
                    continue

                # 2. Check for specific directory names (e.g., docs, examples, src)
                #    These are top-level or significant directories to exclude.
                excluded_exact_segments = {"docs", "examples", "src"}
                # Check if any *part* of the path is one of these exact segments.
                # This is more about excluding whole directory trees like 'src/' or 'docs/'.
                for i, dir_part_content in enumerate(
                    path_parts[:-1]
                ):  # Iterate over directory parts
                    if lower_path_parts[i] in excluded_exact_segments:
                        # Check if this segment is a top-level segment or a direct child of project_root
                        # to avoid overly broad exclusions if a nested dir has this name.
                        # For 'src', we typically mean 'project_root/src'.
                        # If path_parts = ('src', 'mypkg', 'test_something.py'), lower_path_parts[0] is 'src'.
                        if i == 0:  # If the segment is the first part of the relative path
                            self.logger.debug(
                                f"Excluding '{relative_path_str}' because it is within an excluded top-level directory "
                                f"segment '{dir_part_content}'."
                            )
                            is_excluded = True
                            break
                if is_excluded:
                    continue

                # 3. Check for Python library paths (e.g., .../lib/pythonX.Y/...)
                for i, dir_part_content in enumerate(path_parts[:-1]):
                    if lower_path_parts[i] == "lib":
                        # Check if there's a next segment and it starts with 'python'
                        if (i + 1) < len(path_parts[:-1]) and lower_path_parts[i + 1].startswith(
                            "python"
                        ):
                            self.logger.debug(
                                f"Excluding '{relative_path_str}' due to Python lib path pattern "
                                f"'{dir_part_content}/{path_parts[i + 1]}'."
                            )
                            is_excluded = True
                            break
                if is_excluded:
                    continue

                # --- Test File Identification Logic (Refined) ---
                # A file is considered a test file if its name matches the pattern
                # AND it's not in an excluded path.
                # Being in a "tests" directory is a convention, but the filename must still match.

                is_test_file_by_name = file_name_lower.startswith(
                    "test_"
                ) or file_name_lower.endswith("_test.py")

                if not is_test_file_by_name:
                    self.logger.debug(
                        f"Skipping '{relative_path_str}': does not meet test file name criteria "
                        f"(must start with 'test_' or end with '_test.py')."
                    )
                    continue

                # At this point, the file has a test-like name and is not in an excluded path.
                # No further checks on directory names like "test" or "tests" are needed for *inclusion*.
                # The exclusion rules have already handled paths we don't want.

                self.logger.info(
                    f"Discovered potential test file (passes name and path checks): '{relative_path_str}'"
                )
                failure_item = PytestFailure(
                    outcome="discovered",
                    test_name=relative_path_str,
                    test_file=relative_path_str,
                    error_type="discovered_file",
                    error_message="",
                    traceback="",
                    line_number=None,
                )
                discovered_items.append(failure_item)

            self.logger.info(f"Final count of discovered test files: {len(discovered_items)}.")
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
