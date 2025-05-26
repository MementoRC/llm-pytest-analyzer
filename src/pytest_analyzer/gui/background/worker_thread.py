import logging
import threading
import traceback
from typing import Any, Callable, Dict, Optional, Tuple

from PySide6.QtCore import QObject, QThread, Signal, Slot

logger = logging.getLogger(__name__)


class WorkerThread(QThread):
    """
    Executes a callable task in a separate thread.

    Signals:
        result_ready: Emitted when the task completes successfully.
                      Provides task_id and the result.
        error_occurred: Emitted when the task fails due to an exception.
                        Provides task_id and a formatted error message.
        progress_updated: Emitted to report task progress.
                          Provides task_id, percentage, and a message.
                          This signal is typically connected from a ProgressBridge.
    """

    result_ready = Signal(str, object)  # task_id, result
    error_occurred = Signal(str, str)  # task_id, error_message
    # This signal will be connected to by TaskManager, and ProgressBridge will emit to it.
    # Or, TaskManager connects directly to ProgressBridge's signal.
    # Let's have WorkerThread emit its own progress signal, which ProgressBridge can trigger.
    progress_updated = Signal(str, int, str)  # task_id, percentage, message

    def __init__(
        self,
        task_id: str,
        callable_task: Callable,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.task_id = task_id
        self.callable_task = callable_task
        self.args = args if args is not None else ()
        self.kwargs = kwargs if kwargs is not None else {}
        self._is_cancelled = threading.Event()

        # The ProgressBridge will be created by TaskManager and passed in kwargs if needed
        # It will connect its signal to self.progress_updated_slot

    def run(self) -> None:
        """Execute the task."""
        try:
            logger.info(
                f"WorkerThread (task_id: {self.task_id}): Starting task {self.callable_task.__name__}"
            )
            # Prepare kwargs for the callable task, potentially including cancellation event and progress bridge
            # For now, cancellation is best-effort by the callable task if it's designed for it.
            # If 'cancellation_event' is expected by callable_task, it should be in self.kwargs.
            # If 'progress' (ProgressBridge) is expected, it should be in self.kwargs.

            # Example of how cancellation_event could be passed if tasks support it:
            # effective_kwargs = {**self.kwargs}
            # if "cancellation_event" in inspect.signature(self.callable_task).parameters:
            #    effective_kwargs["cancellation_event"] = self._is_cancelled

            result = self.callable_task(*self.args, **self.kwargs)

            if self._is_cancelled.is_set():
                logger.info(
                    f"WorkerThread (task_id: {self.task_id}): Task was cancelled during execution."
                )
                self.error_occurred.emit(self.task_id, "Task cancelled")
            else:
                logger.info(f"WorkerThread (task_id: {self.task_id}): Task completed successfully.")
                self.result_ready.emit(self.task_id, result)

        except Exception as e:
            logger.error(
                f"WorkerThread (task_id: {self.task_id}): Error during task execution: {e}",
                exc_info=True,
            )
            error_msg = f"Error in task {self.task_id} ({self.callable_task.__name__}):\n{type(e).__name__}: {e}\n\nTraceback:\n{traceback.format_exc()}"
            self.error_occurred.emit(self.task_id, error_msg)

    def cancel(self) -> None:
        """Signal the task to cancel."""
        logger.info(f"WorkerThread (task_id: {self.task_id}): Cancellation requested.")
        self._is_cancelled.set()

    @Slot(str, int, str)
    def on_progress_bridge_update(self, task_id: str, percentage: int, message: str) -> None:
        """Slot to receive progress from ProgressBridge and re-emit."""
        if task_id == self.task_id:  # Ensure it's for this worker's task
            self.progress_updated.emit(self.task_id, percentage, message)
