import logging
import uuid
from typing import Any, Callable, Dict, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from .progress_bridge import ProgressBridge, RichTaskID
from .worker_thread import WorkerThread

logger = logging.getLogger(__name__)


class TaskManager(QObject):
    """
    Manages and orchestrates background tasks using WorkerThreads.
    """

    task_started = pyqtSignal(str, str)  # task_id, description (e.g. callable name)
    task_progress = pyqtSignal(str, int, str)  # task_id, percentage, message
    task_completed = pyqtSignal(str, object)  # task_id, result
    task_failed = pyqtSignal(str, str)  # task_id, error_message

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._active_workers: Dict[str, WorkerThread] = {}
        self._progress_bridges: Dict[str, ProgressBridge] = {}
        self._next_rich_task_id_base = 0  # To ensure unique rich task IDs for analyzer_service

    def submit_task(
        self,
        callable_task: Callable,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        use_progress_bridge: bool = False,
    ) -> str:
        """
        Submits a task for background execution.

        Args:
            callable_task: The function or method to execute.
            args: Positional arguments for the callable.
            kwargs: Keyword arguments for the callable.
            task_id: Optional custom ID for the task. If None, one is generated.
            use_progress_bridge: If True, a ProgressBridge is created and passed
                                 as 'progress' and its main rich TaskID as 'task_id'
                                 (or 'parent_task_id') in kwargs to the callable_task.

        Returns:
            The ID of the submitted task.
        """
        actual_task_id = task_id if task_id is not None else uuid.uuid4().hex
        effective_kwargs = kwargs.copy() if kwargs is not None else {}

        worker = WorkerThread(actual_task_id, callable_task, args, effective_kwargs, parent=self)

        if use_progress_bridge:
            # Assign a unique rich task ID for this GUI task to pass to analyzer_service
            # This ID will be used by analyzer_service as its top-level/parent task ID.
            main_rich_id_for_service = RichTaskID(self._next_rich_task_id_base)
            self._next_rich_task_id_base += 1000  # Increment base for next task, ensuring space

            progress_bridge = ProgressBridge(actual_task_id, main_rich_id_for_service, parent=self)
            progress_bridge.qt_progress_signal.connect(
                worker.on_progress_bridge_update
            )  # Bridge -> Worker
            self._progress_bridges[actual_task_id] = progress_bridge

            # Pass the bridge and the designated rich TaskID to the callable
            effective_kwargs["progress"] = progress_bridge
            # PytestAnalyzerService methods expect 'task_id' or 'parent_task_id' for rich progress
            # We need to check which one the specific callable_task expects.
            # Common names are 'task_id' (for run_pytest_only) or 'parent_task_id' (for _generate_suggestions context)
            # For simplicity, let's try to add both if not present, or update if one is.
            # This is a heuristic. Ideally, the caller specifies the kwarg name.
            if (
                "parent_task_id" in effective_kwargs
                or "parent_task_id" in callable_task.__code__.co_varnames
            ):
                effective_kwargs["parent_task_id"] = main_rich_id_for_service
            elif "task_id" in effective_kwargs or "task_id" in callable_task.__code__.co_varnames:
                effective_kwargs["task_id"] = main_rich_id_for_service
            else:
                # Defaulting to 'task_id' if unsure, might need adjustment based on callable_task signature
                effective_kwargs["task_id"] = main_rich_id_for_service

            worker.kwargs = effective_kwargs  # Update worker's kwargs

        worker.result_ready.connect(self._on_worker_result_ready)
        worker.error_occurred.connect(self._on_worker_error_occurred)
        worker.progress_updated.connect(self._on_worker_progress_updated)  # Worker -> TaskManager

        self._active_workers[actual_task_id] = worker
        worker.start()
        logger.info(f"Task '{actual_task_id}' ({callable_task.__name__}) submitted and started.")
        self.task_started.emit(actual_task_id, callable_task.__name__)
        return actual_task_id

    def cancel_task(self, task_id: str) -> None:
        """Requests cancellation of an active task."""
        worker = self._active_workers.get(task_id)
        if worker:
            logger.info(f"Requesting cancellation for task '{task_id}'.")
            worker.cancel()
        else:
            logger.warning(f"Attempted to cancel non-existent task '{task_id}'.")

    @pyqtSlot(str, object)
    def _on_worker_result_ready(self, task_id: str, result: Any) -> None:
        logger.info(f"Task '{task_id}' completed successfully.")
        self.task_completed.emit(task_id, result)
        self._cleanup_task(task_id)

    @pyqtSlot(str, str)
    def _on_worker_error_occurred(self, task_id: str, error_message: str) -> None:
        logger.error(f"Task '{task_id}' failed: {error_message}")
        self.task_failed.emit(task_id, error_message)
        self._cleanup_task(task_id)

    @pyqtSlot(str, int, str)
    def _on_worker_progress_updated(self, task_id: str, percentage: int, message: str) -> None:
        # This signal comes from WorkerThread, which got it from ProgressBridge
        logger.debug(f"Task '{task_id}' progress: {percentage}% - {message}")
        self.task_progress.emit(task_id, percentage, message)

    def _cleanup_task(self, task_id: str) -> None:
        """Removes a completed or failed task from active tracking."""
        if task_id in self._active_workers:
            worker = self._active_workers.pop(task_id)
            worker.deleteLater()  # Schedule QThread for deletion
        if task_id in self._progress_bridges:
            bridge = self._progress_bridges.pop(task_id)
            bridge.deleteLater()  # Schedule QObject for deletion
        logger.debug(f"Cleaned up resources for task '{task_id}'.")

    def active_task_count(self) -> int:
        return len(self._active_workers)
