import logging
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Signal

# Rich's TaskID is typically an int, but can be any hashable.
# For simplicity, we'll use int for rich_task_id.
RichTaskID = int

logger = logging.getLogger(__name__)


class ProgressBridge(QObject):
    """
    Adapts progress updates from a rich.progress-like API to Qt signals.

    This class is intended to be passed as the 'progress' argument to
    core services (like PytestAnalyzerService) that use rich.progress
    for internal progress tracking.
    """

    # Signal: gui_task_id, percentage, message
    qt_progress_signal = Signal(str, int, str)

    def __init__(
        self,
        gui_task_id: str,
        main_rich_task_id_for_service: RichTaskID,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.gui_task_id = gui_task_id
        self.main_rich_task_id = main_rich_task_id_for_service
        self._rich_task_counter: RichTaskID = 0  # Counter for generating unique rich task IDs
        self._managed_rich_tasks: Dict[RichTaskID, Dict[str, Any]] = {}
        logger.debug(
            f"ProgressBridge for GUI task '{gui_task_id}' initialized, expecting main rich task ID {main_rich_task_id_for_service}."
        )

    def add_task(
        self,
        description: str,
        total: Optional[float] = 1.0,
        parent: Optional[RichTaskID] = None,
        **fields: Any,
    ) -> RichTaskID:
        """Mimics rich.progress.Progress.add_task."""
        new_rich_id = self._rich_task_counter
        self._rich_task_counter += 1

        # Ensure total is at least a small positive number if not None, or 1.0 if None
        effective_total = total if total is not None and total > 0 else 1.0

        self._managed_rich_tasks[new_rich_id] = {
            "description": description,
            "total": effective_total,
            "current": 0.0,
            "parent_rich_id": parent,
            "visible": fields.get("visible", True),  # Rich progress tasks can be invisible
        }
        logger.debug(
            f"ProgressBridge (GUI task '{self.gui_task_id}'): Added rich task {new_rich_id} ('{description}') with parent {parent}"
        )

        # Initial update if this task is a child of the main one
        if parent == self.main_rich_task_id:
            self._emit_overall_progress()
        return new_rich_id

    def update(
        self,
        task_id: RichTaskID,  # This is the RichTaskID returned by add_task
        description: Optional[str] = None,
        completed: Optional[
            bool
        ] = None,  # Rich uses 'completed' as a float amount or bool for full completion
        advance: Optional[float] = None,
        total: Optional[float] = None,  # Renamed from 'total_val' for consistency with rich
        visible: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """Mimics rich.progress.Progress.update."""
        rich_task = self._managed_rich_tasks.get(task_id)
        if not rich_task:
            logger.warning(
                f"ProgressBridge (GUI task '{self.gui_task_id}'): Update called for unknown rich task {task_id}"
            )
            return

        if description is not None:
            rich_task["description"] = description
        if total is not None and total > 0:  # Ensure total is positive
            rich_task["total"] = total
        if advance is not None:
            rich_task["current"] = min(rich_task["current"] + advance, rich_task["total"])

        # Rich's 'completed' can be a boolean or a float value for the amount completed.
        # Here, we interpret boolean 'completed=True' as task fully done.
        # If 'completed' is a float, it's treated like 'current'.
        if isinstance(completed, bool) and completed:
            rich_task["current"] = rich_task["total"]
        elif isinstance(completed, (int, float)):  # If completed is a numeric value
            rich_task["current"] = min(float(completed), rich_task["total"])

        if visible is not None:
            rich_task["visible"] = visible

        logger.debug(
            f"ProgressBridge (GUI task '{self.gui_task_id}'): Updated rich task {task_id} ('{rich_task['description']}'). Current: {rich_task['current']}, Total: {rich_task['total']}"
        )

        # Emit progress if this task or its parent is the main rich task
        if (
            rich_task["parent_rich_id"] == self.main_rich_task_id
            or task_id == self.main_rich_task_id
        ):
            self._emit_overall_progress()

    def _emit_overall_progress(self) -> None:
        """Calculates and emits the overall progress for the GUI task."""
        current_sum = 0.0
        total_sum = 0.0
        active_descriptions = []

        # Consider the main task itself if it has progress
        main_task_data = self._managed_rich_tasks.get(self.main_rich_task_id)
        if main_task_data and main_task_data["visible"]:
            # If the main task has its own total, it might represent the overall progress directly
            # This logic depends on how analyzer_service structures its tasks.
            # For now, we sum children, but if main_rich_task_id is updated directly, that's simpler.
            # Let's assume main_rich_task_id is a container, and its children define progress.
            pass

        for tid, t_data in self._managed_rich_tasks.items():
            if t_data["parent_rich_id"] == self.main_rich_task_id and t_data["visible"]:
                current_sum += t_data["current"]
                total_sum += t_data["total"]
                if t_data["current"] < t_data["total"]:
                    active_descriptions.append(t_data["description"])

        if (
            not active_descriptions
            and main_task_data
            and main_task_data["visible"]
            and main_task_data["current"] < main_task_data["total"]
        ):
            active_descriptions.append(main_task_data["description"])

        percentage = 0
        if total_sum > 0:
            percentage = int((current_sum / total_sum) * 100)
        elif (
            main_task_data and main_task_data["total"] > 0 and main_task_data["visible"]
        ):  # Fallback to main task if no children sum
            percentage = int((main_task_data["current"] / main_task_data["total"]) * 100)

        # Ensure percentage is capped at 100
        percentage = min(percentage, 100)

        message = (
            "; ".join(active_descriptions)
            if active_descriptions
            else (
                main_task_data["description"]
                if main_task_data and main_task_data["visible"]
                else "Processing..."
            )
        )

        if current_sum >= total_sum and total_sum > 0:  # All children complete
            message = (
                f"{main_task_data['description']}: Complete" if main_task_data else "Completed"
            )
            percentage = 100
        elif (
            main_task_data
            and main_task_data["current"] >= main_task_data["total"]
            and main_task_data["total"] > 0
            and main_task_data["visible"]
        ):
            message = f"{main_task_data['description']}: Complete"
            percentage = 100

        logger.debug(
            f"ProgressBridge (GUI task '{self.gui_task_id}'): Emitting progress: {percentage}%, Message: '{message}'"
        )
        self.qt_progress_signal.emit(self.gui_task_id, percentage, message)

    # Add dummy methods for other rich.progress.Progress API if needed by analyzer_service
    def start_task(self, task_id: RichTaskID) -> None:
        logger.debug(
            f"ProgressBridge (GUI task '{self.gui_task_id}'): start_task called for rich task {task_id} (no-op)"
        )
        pass

    def stop_task(self, task_id: RichTaskID) -> None:
        logger.debug(
            f"ProgressBridge (GUI task '{self.gui_task_id}'): stop_task called for rich task {task_id} (no-op)"
        )
        pass

    def remove_task(self, task_id: RichTaskID) -> None:
        logger.debug(
            f"ProgressBridge (GUI task '{self.gui_task_id}'): remove_task called for rich task {task_id}"
        )
        if task_id in self._managed_rich_tasks:
            del self._managed_rich_tasks[task_id]
        self._emit_overall_progress()  # Re-evaluate progress

    @property
    def tasks(self):  # analyzer_service.Context.cleanup_progress_tasks checks this
        # Return a list-like object of task-like objects that have an 'id' attribute
        class SimpleRichTask:
            def __init__(self, task_id):
                self.id = task_id

        return [
            SimpleRichTask(tid)
            for tid in self._managed_rich_tasks.keys()
            if self._managed_rich_tasks[tid].get("visible", True)
        ]

    def get_task(
        self, task_id: RichTaskID
    ):  # analyzer_service.Context.cleanup_progress_tasks uses this
        if task_id in self._managed_rich_tasks:
            # Return a mock task object that rich.Progress.get_task would return
            # For now, just returning the dict, but ideally a small class.
            class MockTask:
                def __init__(self, task_id, data):
                    self.id = task_id
                    self.description = data.get("description", "")
                    self.completed = data.get("current", 0)
                    self.total = data.get("total", 1)
                    # Add other attributes if needed by analyzer_service

            return MockTask(task_id, self._managed_rich_tasks[task_id])
        raise KeyError(f"Task {task_id} not found")
