import logging
from typing import Any, Callable, Dict, Optional, Tuple

from PySide6.QtCore import QObject

# Forward declaration for type hinting if TaskManager is in a different module
# and to avoid circular imports if BaseController is imported by TaskManager's module.
# However, here TaskManager is in a sub-module, so direct import should be fine.
from ..background.task_manager import TaskManager  # Adjusted import

logger = logging.getLogger(__name__)


class BaseController(QObject):
    """Abstract base class for all controllers."""

    def __init__(
        self, parent: Optional[QObject] = None, task_manager: Optional[TaskManager] = None
    ):  # Added task_manager
        """
        Initialize the base controller.

        Args:
            parent: Optional parent QObject.
            task_manager: Optional TaskManager instance for background tasks.
        """
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.task_manager = task_manager  # Store task_manager
        self.logger.info(f"{self.__class__.__name__} initialized")

    def handle_error(self, message: str, error: Exception = None) -> None:
        """
        Handle an error, logging it.

        Args:
            message: The error message.
            error: The exception, if any.
        """
        self.logger.error(message)
        if error:
            self.logger.exception(error)

    def submit_background_task(
        self,
        callable_task: Callable,
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        use_progress_bridge: bool = False,
    ) -> Optional[str]:
        """
        Helper to submit a task to the TaskManager.

        Args:
            callable_task: The function to execute.
            args: Positional arguments for the callable.
            kwargs: Keyword arguments for the callable.
            use_progress_bridge: Whether to set up a ProgressBridge for the task.

        Returns:
            The task ID if submitted, else None.
        """
        if not self.task_manager:
            self.logger.error("TaskManager not available. Cannot submit background task.")
            return None

        task_id = self.task_manager.submit_task(
            callable_task,
            args=args,
            kwargs=kwargs,
            use_progress_bridge=use_progress_bridge,
        )
        return task_id
