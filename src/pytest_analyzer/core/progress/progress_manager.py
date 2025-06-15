import logging
from typing import Any, Dict, Optional

from rich.progress import Progress, TaskID

from ..interfaces.protocols import ProgressManager

logger = logging.getLogger(__name__)


class RichProgressManager(ProgressManager):
    """Manages progress updates using rich.progress."""

    def __init__(
        self,
        progress: Optional[Progress] = None,
        parent_task_id: Optional[TaskID] = None,
        quiet: bool = False,
    ):
        self.progress = progress
        self.parent_task_id = parent_task_id
        self.quiet = quiet
        self.progress_tasks: Dict[str, TaskID] = {}

    def create_task(self, key: str, description: str, **kwargs) -> Optional[TaskID]:
        """
        Create a progress task and store its ID for later reference.
        """
        if self.progress and self.parent_task_id is not None:
            if "parent" not in kwargs:
                kwargs["parent"] = self.parent_task_id

            task_id = self.progress.add_task(description, **kwargs)
            self.progress_tasks[key] = task_id
            return task_id
        return None

    def update_task(
        self,
        key: str,
        description: Optional[str] = None,
        completed: bool = False,
        **kwargs,
    ) -> None:
        """
        Update a progress task by its key.
        """
        if self.progress and key in self.progress_tasks:
            task_id = self.progress_tasks[key]
            update_kwargs: Dict[str, Any] = {}

            if description:
                update_kwargs["description"] = description
            if completed:
                update_kwargs["completed"] = True

            update_kwargs.update(kwargs)

            self.progress.update(task_id, **update_kwargs)

    def cleanup_tasks(self) -> None:
        """Mark all progress tasks as completed to ensure clean UI."""
        if self.progress:
            for key, task_id in self.progress_tasks.items():
                try:
                    task_fn = getattr(self.progress, "get_task", None)
                    if task_fn and task_fn(task_id):
                        self.progress.update(task_id, completed=True)
                except Exception as e:
                    logger.debug(f"Error cleaning up progress task {key}: {e}")
