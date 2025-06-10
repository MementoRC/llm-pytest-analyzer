"""Task registration and discovery system for the LLM Task Framework."""

from typing import Any, Callable, Dict, List, Optional


class TaskRegistry:
    """
    Registry for task definitions, enabling plugin-based extensibility and metadata management.

    Supports plugin-style architecture and dynamic discovery/loading of tasks.
    """

    def __init__(self):
        self._tasks: Dict[str, Any] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def register(
        self, task_type: str, definition: Any, metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Register a new task definition.

        Args:
            task_type: The string identifier for the task type.
            definition: The task class or callable.
            metadata: Optional metadata dictionary.
        """
        self._tasks[task_type] = definition
        self._metadata[task_type] = metadata or {}

    def get(self, task_type: str) -> Optional[Any]:
        """
        Retrieve a task definition by type.

        Args:
            task_type: The string identifier for the task type.

        Returns:
            Task definition or None.
        """
        return self._tasks.get(task_type)

    def get_metadata(self, task_type: str) -> Dict[str, Any]:
        """
        Get metadata for a registered task.

        Args:
            task_type: The string identifier for the task type.

        Returns:
            Metadata dictionary.
        """
        return self._metadata.get(task_type, {})

    def list(self) -> List[str]:
        """
        List all registered task types.

        Returns:
            List of task type names.
        """
        return list(self._tasks.keys())

    def discover(self, plugin_loader: Optional[Callable] = None):
        """
        Discover and load tasks from plugins.

        Args:
            plugin_loader: Optional callable to load plugins.
        """
        if plugin_loader:
            plugin_loader(self)
