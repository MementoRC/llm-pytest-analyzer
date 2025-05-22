import logging
from typing import TYPE_CHECKING, Any, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QMessageBox

from ...core.models.pytest_failure import PytestFailure
from .base_controller import BaseController

if TYPE_CHECKING:
    from ...core.analyzer_service import PytestAnalyzerService
    from ..background.task_manager import TaskManager

logger = logging.getLogger(__name__)


class TestDiscoveryController(BaseController):
    """Controller for discovering tests using 'pytest --collect-only'."""

    tests_discovered = pyqtSignal(list)  # Emits List[PytestFailure] (node IDs)
    discovery_started = pyqtSignal(str)  # Emits a message
    discovery_finished = pyqtSignal(str)  # Emits a message (success or failure)

    def __init__(
        self,
        analyzer_service: "PytestAnalyzerService",
        parent: Optional[QObject] = None,
        task_manager: Optional["TaskManager"] = None,
    ):
        super().__init__(parent, task_manager=task_manager)
        self.analyzer_service = analyzer_service
        self._current_discovery_task_id: Optional[str] = None

        if self.task_manager:
            self.task_manager.task_completed.connect(self._handle_task_completion)
            self.task_manager.task_failed.connect(self._handle_task_failure)

    @pyqtSlot()
    def request_discover_tests(self) -> None:
        """Initiates test discovery in the background."""
        if self._current_discovery_task_id and self.task_manager:
            # Optionally, cancel the previous task or inform the user
            self.logger.info("Test discovery is already in progress.")
            # self.task_manager.cancel_task(self._current_discovery_task_id)
            # For now, let's just prevent concurrent discoveries from this controller
            QMessageBox.information(
                None, "Test Discovery", "A discovery process is already running."
            )
            return

        self.logger.info("Requesting test discovery.")
        self.discovery_started.emit("Starting test discovery...")

        # Determine the path to run discovery on (e.g., project root)
        # Assuming project_root is a Path object
        project_root_path = self.analyzer_service.settings.project_root
        if not project_root_path:
            self.logger.error("Project root not set in settings. Cannot discover tests.")
            self.discovery_finished.emit("Discovery failed: Project root not configured.")
            QMessageBox.critical(
                None, "Discovery Error", "Project root is not configured in settings."
            )
            return

        test_path = str(project_root_path)
        self.logger.info(f"Discovering tests in: {test_path}")

        args = (test_path,)
        # run_pytest_only expects pytest_args, quiet, progress, task_id
        kwargs = {
            "pytest_args": ["--collect-only", "-q"],  # -q for less verbose collection
            "quiet": True,  # Suppress run_pytest_only's own potential console output
        }

        task_id = self.submit_background_task(
            callable_task=self.analyzer_service.run_pytest_only,
            args=args,
            kwargs=kwargs,
            use_progress_bridge=True,  # So progress updates from service are caught
        )

        if task_id:
            self._current_discovery_task_id = task_id
            self.logger.info(f"Test discovery task submitted with ID: {task_id}")
            # Global task started message will be handled by MainController
        else:
            self.logger.error("Failed to submit test discovery task.")
            self.discovery_finished.emit("Discovery failed: Could not start background task.")
            QMessageBox.warning(
                None, "Discovery Error", "Failed to start the test discovery process."
            )

    @pyqtSlot(str, object)
    def _handle_task_completion(self, task_id: str, result: Any) -> None:
        if task_id == self._current_discovery_task_id:
            self.logger.info(f"Test discovery task {task_id} completed.")
            self._current_discovery_task_id = None

            if isinstance(result, list) and (not result or isinstance(result[0], PytestFailure)):
                collected_items: List[PytestFailure] = result
                self.logger.info(f"Discovered {len(collected_items)} test items.")
                self.tests_discovered.emit(collected_items)
                self.discovery_finished.emit(
                    f"Test discovery complete. Found {len(collected_items)} items."
                )
            else:
                self.logger.error(
                    f"Discovery task {task_id} returned unexpected result type: {type(result)}"
                )
                self.discovery_finished.emit("Discovery failed: Unexpected result from collection.")
                QMessageBox.warning(
                    None, "Discovery Error", "Test discovery process returned an unexpected result."
                )

    @pyqtSlot(str, str)
    def _handle_task_failure(self, task_id: str, error_message: str) -> None:
        if task_id == self._current_discovery_task_id:
            self.logger.error(f"Test discovery task {task_id} failed: {error_message}")
            self._current_discovery_task_id = None
            self.discovery_finished.emit(f"Test discovery failed: {error_message.splitlines()[0]}")
            # Global task failed message will be handled by MainController, which shows a QMessageBox
            # QMessageBox.critical(None, "Discovery Error", f"Test discovery process failed:\n{error_message.splitlines()[0]}")
