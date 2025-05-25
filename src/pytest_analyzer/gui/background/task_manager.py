import gc  # Added gc
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple  # Added List

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot  # Added QTimer

from .progress_bridge import ProgressBridge, RichTaskID
from .worker_thread import WorkerThread

logger = logging.getLogger(__name__)


class TaskManager(QObject):
    """
    Manages and orchestrates background tasks using WorkerThreads.
    Tasks are processed serially to conserve resources.
    """

    task_started = pyqtSignal(str, str)  # task_id, description
    task_progress = pyqtSignal(str, int, str)  # task_id, percentage, message
    task_completed = pyqtSignal(str, object)  # task_id, result
    task_failed = pyqtSignal(str, str)  # task_id, error_message
    task_resources_released = pyqtSignal(str)  # task_id

    # Delay in milliseconds before starting the next task after one finishes, allows for cleanup
    POST_TASK_CLEANUP_DELAY_MS = 250

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._active_workers: Dict[str, WorkerThread] = {}
        self._progress_bridges: Dict[str, ProgressBridge] = {}
        self._next_rich_task_id_base = 0

        # Queue for tasks waiting to be processed
        self._task_queue: List[
            Tuple[str, Callable[..., Any], Optional[Tuple[Any, ...]], Dict[str, Any], bool]
        ] = []  # Stores (task_id, callable_task, args, original_kwargs, use_progress_bridge)
        # ID of the task currently being processed by a worker
        self._current_processing_task_id: Optional[str] = None

    def submit_task(
        self,
        callable_task: Callable[..., Any],
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        use_progress_bridge: bool = False,
    ) -> str:
        """
        Submits a task for background execution. Tasks are queued and processed serially.
        """
        actual_task_id = task_id if task_id is not None else uuid.uuid4().hex

        # kwargs here are the original ones intended for the callable_task by the submitter
        prepared_kwargs = kwargs.copy() if kwargs is not None else {}

        if self._current_processing_task_id is None:
            logger.info(
                f"No task currently processing. Starting task '{actual_task_id}' immediately."
            )
            self._start_processing_task(
                actual_task_id, callable_task, args, prepared_kwargs, use_progress_bridge
            )
        else:
            self._task_queue.append(
                (actual_task_id, callable_task, args, prepared_kwargs, use_progress_bridge)
            )
            logger.info(
                f"Task '{actual_task_id}' ({callable_task.__name__}) queued. "
                f"Current processing: '{self._current_processing_task_id}'. "
                f"Queue size: {len(self._task_queue)}."
            )

        # Emit task_started when submitted, whether it starts immediately or is queued.
        self.task_started.emit(actual_task_id, callable_task.__name__)
        return actual_task_id

    def _start_processing_task(
        self,
        task_id: str,
        callable_task: Callable[..., Any],
        args: Optional[Tuple[Any, ...]],
        original_kwargs: Dict[str, Any],  # App-level kwargs for the callable
        use_progress_bridge: bool,
    ) -> None:
        if self._current_processing_task_id is not None:
            # This case should ideally not be hit if logic is correct, but as a safeguard:
            logger.error(
                f"Attempted to start task '{task_id}' while task '{self._current_processing_task_id}' is already processing. Re-queuing."
            )
            self._task_queue.insert(
                0, (task_id, callable_task, args, original_kwargs, use_progress_bridge)
            )  # Insert at front if it was meant to be next
            QTimer.singleShot(0, self._process_next_task_in_queue)  # Trigger queue processing check
            return

        self._current_processing_task_id = task_id
        logger.info(f"Starting processing for task '{task_id}' ({callable_task.__name__}).")

        # worker_kwargs are for the WorkerThread and ultimately for the callable_task
        worker_kwargs = original_kwargs.copy()

        if use_progress_bridge:
            main_rich_id_for_service = RichTaskID(self._next_rich_task_id_base)
            self._next_rich_task_id_base += 1000  # Increment for next task

            progress_bridge = ProgressBridge(task_id, main_rich_id_for_service, parent=self)
            self._progress_bridges[task_id] = progress_bridge

            worker_kwargs["progress"] = progress_bridge
            if (
                "parent_task_id" in worker_kwargs
                or "parent_task_id" in callable_task.__code__.co_varnames
            ):
                worker_kwargs["parent_task_id"] = main_rich_id_for_service
            elif "task_id" in worker_kwargs or "task_id" in callable_task.__code__.co_varnames:
                worker_kwargs["task_id"] = main_rich_id_for_service
            else:
                worker_kwargs["task_id"] = main_rich_id_for_service

        worker = WorkerThread(task_id, callable_task, args, worker_kwargs, parent=self)

        if use_progress_bridge and task_id in self._progress_bridges:
            self._progress_bridges[task_id].qt_progress_signal.connect(
                worker.on_progress_bridge_update
            )

        worker.result_ready.connect(self._on_worker_result_ready)
        worker.error_occurred.connect(self._on_worker_error_occurred)
        worker.progress_updated.connect(self._on_worker_progress_updated)

        self._active_workers[task_id] = worker
        worker.start()
        logger.info(f"Worker for task '{task_id}' ({callable_task.__name__}) started.")

    def cancel_task(self, task_id: str) -> None:
        """Requests cancellation of an active or queued task."""
        # Check if the task is in the queue
        for i, queued_task_details in enumerate(self._task_queue):
            if queued_task_details[0] == task_id:  # task_id is the first element
                self._task_queue.pop(i)
                logger.info(f"Task '{task_id}' removed from queue upon cancellation request.")
                self.task_failed.emit(task_id, "Task cancelled while in queue")
                self.task_resources_released.emit(task_id)
                return

        # If not in queue, check if it's the currently processing task
        if task_id == self._current_processing_task_id:
            worker = self._active_workers.get(task_id)
            if worker:
                logger.info(f"Requesting cancellation for currently processing task '{task_id}'.")
                worker.cancel()  # WorkerThread will typically emit error_occurred
            else:  # Should not happen if _current_processing_task_id is valid
                logger.warning(
                    f"Task '{task_id}' is current processing task, but no worker found in _active_workers. "
                    "This indicates an inconsistent state. Emitting failure."
                )
                self.task_failed.emit(
                    task_id, "Cancellation failed: worker not found for current task"
                )
                self._handle_task_termination(task_id)  # Attempt cleanup
        elif task_id in self._active_workers:  # In active_workers but not current (e.g. finishing)
            worker = self._active_workers.get(task_id)
            if worker:
                logger.warning(
                    f"Task '{task_id}' found in active workers but is not the current processing task. "
                    f"Attempting to cancel. Current processing: {self._current_processing_task_id}"
                )
                worker.cancel()
        else:
            logger.warning(
                f"Attempted to cancel task '{task_id}', but it was not found in the queue or active workers."
            )

    @pyqtSlot(str, object)
    def _on_worker_result_ready(self, task_id: str, result: Any) -> None:
        logger.info(f"Task '{task_id}' completed successfully.")
        self.task_completed.emit(task_id, result)
        self._handle_task_termination(task_id)

    @pyqtSlot(str, str)
    def _on_worker_error_occurred(self, task_id: str, error_message: str) -> None:
        logger.error(f"Task '{task_id}' failed: {error_message}")
        self.task_failed.emit(task_id, error_message)
        self._handle_task_termination(task_id)

    def _handle_task_termination(self, task_id: str) -> None:
        """Common logic for when a task ends (completes, fails, or is cancelled leading to error)."""
        self._cleanup_task(task_id)  # Handles worker and bridge removal/deletion

        if task_id == self._current_processing_task_id:
            self._current_processing_task_id = None
            logger.debug(f"Cleared _current_processing_task_id (was {task_id}).")
        else:
            logger.warning(
                f"Terminated task '{task_id}' was not the _current_processing_task_id "
                f"('{self._current_processing_task_id}'). State might be unusual."
            )
            # Safeguard: if current processing ID still points to this task, clear it.
            if self._current_processing_task_id == task_id:
                self._current_processing_task_id = None
                logger.debug(f"Cleared _current_processing_task_id (was {task_id}) as a safeguard.")

        logger.debug("Forcing garbage collection after task termination.")
        gc.collect()

        logger.debug(
            f"Scheduling next task processing with a delay of {self.POST_TASK_CLEANUP_DELAY_MS}ms."
        )
        QTimer.singleShot(self.POST_TASK_CLEANUP_DELAY_MS, self._process_next_task_in_queue)

    @pyqtSlot()
    def _process_next_task_in_queue(self) -> None:
        if not self._task_queue:
            logger.debug("Task queue is empty. No new task to start.")
            return
        if self._current_processing_task_id is not None:
            logger.debug(
                f"A task ('{self._current_processing_task_id}') is already processing. "
                "Cannot start new task from queue yet."
            )
            return

        logger.info(
            f"Processing next task from queue. Queue size before pop: {len(self._task_queue)}"
        )
        (
            task_id,
            callable_task,
            args,
            kwargs,
            use_progress_bridge,
        ) = self._task_queue.pop(0)

        self._start_processing_task(task_id, callable_task, args, kwargs, use_progress_bridge)

    @pyqtSlot(str, int, str)
    def _on_worker_progress_updated(self, task_id: str, percentage: int, message: str) -> None:
        logger.debug(f"Task '{task_id}' progress: {percentage}% - {message}")
        self.task_progress.emit(task_id, percentage, message)

    def _cleanup_task(self, task_id: str) -> None:
        """Removes a task from active tracking and schedules its Qt resources for deletion.
        This method no longer uses psutil.
        """
        logger.debug(f"Starting cleanup for task {task_id}")

        worker = self._active_workers.pop(task_id, None)
        if worker:
            logger.debug(
                f"Worker thread {task_id} found for cleanup. isRunning: {worker.isRunning()}"
            )
            if worker.isRunning():
                logger.debug(f"Requesting worker thread {task_id} to quit...")
                worker.quit()  # Request graceful termination
                if not worker.wait(3000):  # Wait up to 3 seconds for graceful exit
                    logger.warning(
                        f"Worker thread {task_id} did not stop gracefully after quit(). Forcing termination."
                    )
                    worker.terminate()  # Force terminate if it doesn't stop
                    if not worker.wait(2000):  # Wait for termination to complete
                        logger.error(
                            f"Worker thread {task_id} failed to terminate after forced attempt."
                        )

            worker.deleteLater()
            logger.debug(f"Worker thread {task_id} scheduled for deletion.")
        else:
            logger.debug(
                f"No active worker found for task_id {task_id} during cleanup (already removed or never fully started)."
            )

        bridge = self._progress_bridges.pop(task_id, None)
        if bridge:
            bridge.deleteLater()
            logger.debug(f"Progress bridge for task {task_id} scheduled for deletion.")
        else:
            logger.debug(f"No progress bridge found for task_id {task_id} during cleanup.")

        logger.debug(f"Cleanup initiated for task '{task_id}'. Emitting task_resources_released.")
        self.task_resources_released.emit(task_id)

    def get_active_task_count(self) -> int:
        """Returns 1 if a task is currently being processed by a worker, 0 otherwise."""
        return 1 if self._current_processing_task_id is not None else 0

    def get_queued_task_count(self) -> int:
        """Returns the number of tasks waiting in the queue."""
        return len(self._task_queue)

    def cleanup_all_tasks(self) -> None:
        """Force cleanup of all active and queued tasks. Called during application shutdown."""
        logger.info(
            f"Initiating cleanup of all tasks. Queued: {len(self._task_queue)}, "
            f"Active Workers Dict Size: {len(self._active_workers)}, "  # For diagnostics
            f"Current Processing Task ID: {self._current_processing_task_id}"
        )

        # Clear the queue - these tasks will not run and are marked as failed/cancelled.
        queued_task_ids_to_fail = [qt[0] for qt in self._task_queue]
        self._task_queue.clear()
        for task_id in queued_task_ids_to_fail:
            logger.info(f"Task '{task_id}' removed from queue during shutdown.")
            self.task_failed.emit(task_id, "Task cancelled due to application shutdown")
            self.task_resources_released.emit(task_id)

        # Attempt to cancel and cleanup the currently processing task, if any.
        current_task_to_cleanup = self._current_processing_task_id
        if current_task_to_cleanup:
            logger.info(
                f"Requesting cancellation for current processing task '{current_task_to_cleanup}' during shutdown."
            )
            worker_to_cancel = self._active_workers.get(current_task_to_cleanup)
            if worker_to_cancel:
                worker_to_cancel.cancel()  # Signal the worker to stop
                # The worker's error/completion signal will trigger _handle_task_termination -> _cleanup_task
                # However, during shutdown, we might not wait for that signal.
                # Forcing cleanup here if it's still in active_workers.
            else:  # If no worker, but was current_processing_task_id
                self._cleanup_task(current_task_to_cleanup)  # Attempt cleanup of bridge etc.

        # Clean up any remaining workers in _active_workers.
        # This includes the one potentially just cancelled if its signals haven't processed, or any others.
        active_task_ids_copy = list(self._active_workers.keys())
        for task_id in active_task_ids_copy:
            logger.debug(f"Force cleaning up worker for task '{task_id}' during shutdown.")
            # Ensure worker is signalled to stop if still running
            worker = self._active_workers.get(task_id)
            if worker and worker.isRunning():
                worker.cancel()  # Prefer cancel over direct quit/terminate if task supports it
            self._cleanup_task(task_id)
            # _cleanup_task removes from _active_workers and emits task_resources_released.
            # If the task hadn't naturally finished, it might not have emitted task_failed/completed.
            # worker.cancel() should lead to task_failed. If not, this task might seem to disappear.
            # For shutdown, this is often acceptable.

        # Final clear of the current processing task ID.
        if self._current_processing_task_id:
            logger.info(
                f"Final clear of _current_processing_task_id: {self._current_processing_task_id} after shutdown cleanup."
            )
            self._current_processing_task_id = None

        logger.info("All tasks cleanup process on shutdown completed.")
