"""
Main facade for the LLM Task Framework.

This module provides the primary entry point for the framework through the
TaskFramework class, which orchestrates task execution using registered
task implementations.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, Union

from llm_task_framework.core.models.config import TaskConfig
from llm_task_framework.core.registry import TaskRegistry
from llm_task_framework.protocols import TaskExecutor, TaskInput, TaskResult
from llm_task_framework.utils.errors import FrameworkError, TaskNotFoundError

logger = logging.getLogger("llm_task_framework.core.facade")


class TaskFramework:
    """
    Main facade for executing LLM-powered tasks.

    This class provides a unified interface for task execution, abstracting
    away the complexity of task registration, dependency injection, and
    workflow orchestration.

    Usage:
        # Create framework instance for a specific task
        framework = TaskFramework.create("pytest_analysis")

        # Execute task
        result = framework.execute(input_data)
    """

    _registry: Optional[TaskRegistry] = None

    def __init__(self, task_type: str, config: Optional[TaskConfig] = None):
        """Initialize framework for a specific task type."""
        self.task_type = task_type
        self.config = config
        self._registry = self.__class__.get_registry()
        self._task_executor = self._resolve_executor(task_type, config)

    @classmethod
    def get_registry(cls) -> TaskRegistry:
        if cls._registry is None:
            cls._registry = TaskRegistry()
        return cls._registry

    @classmethod
    def create(
        cls, task_type: str, config: Optional[TaskConfig] = None
    ) -> "TaskFramework":
        """
        Create a TaskFramework instance for the specified task type.

        Args:
            task_type: Name of the task implementation to use
            config: Optional configuration (uses defaults if not provided)

        Returns:
            Configured TaskFramework instance

        Raises:
            TaskNotFoundError: If the task type is not registered
        """
        logger.debug(
            f"Creating TaskFramework for task_type='{task_type}' with config={config}"
        )
        registry = cls.get_registry()
        if not registry.get(task_type):
            logger.error(f"Task type '{task_type}' is not registered.")
            raise TaskNotFoundError(f"Task type '{task_type}' is not registered.")
        return cls(task_type, config)

    def _resolve_executor(
        self, task_type: str, config: Optional[TaskConfig]
    ) -> TaskExecutor:
        """
        Resolve and instantiate the task executor for the given type.
        """
        definition = self._registry.get(task_type)
        if not definition:
            logger.error(f"Task type '{task_type}' is not registered.")
            raise TaskNotFoundError(f"Task type '{task_type}' is not registered.")
        # Dependency injection: pass config if supported
        if hasattr(definition, "from_config"):
            logger.debug(f"Instantiating '{task_type}' using from_config.")
            return definition.from_config(config)
        elif config is not None:
            logger.debug(f"Instantiating '{task_type}' with config.")
            return definition(config)
        else:
            logger.debug(f"Instantiating '{task_type}' with no config.")
            return definition()

    def execute(
        self, input_data: Union[TaskInput, Dict[str, Any]], **kwargs
    ) -> TaskResult:
        """
        Execute the task with the provided input data.

        Args:
            input_data: Task input data
            **kwargs: Additional execution parameters

        Returns:
            Task execution result

        Raises:
            FrameworkError: If task execution fails
        """
        logger.info(f"Executing task '{self.task_type}' synchronously.")
        try:
            if hasattr(self._task_executor, "run"):
                return self._task_executor.run(input_data, **kwargs)
            elif callable(self._task_executor):
                return self._task_executor(input_data, **kwargs)
            else:
                logger.error(
                    "Task executor is not callable or does not implement 'run'."
                )
                raise FrameworkError("Task executor is not executable.")
        except Exception as exc:
            logger.exception(f"Task execution failed for '{self.task_type}': {exc}")
            raise FrameworkError(f"Task execution failed: {exc}") from exc

    async def execute_async(
        self, input_data: Union[TaskInput, Dict[str, Any]], **kwargs
    ) -> TaskResult:
        """Execute the task asynchronously."""
        logger.info(f"Executing task '{self.task_type}' asynchronously.")
        try:
            if hasattr(
                self._task_executor, "run_async"
            ) and asyncio.iscoroutinefunction(self._task_executor.run_async):
                return await self._task_executor.run_async(input_data, **kwargs)
            elif hasattr(self._task_executor, "run") and asyncio.iscoroutinefunction(
                self._task_executor.run
            ):
                return await self._task_executor.run(input_data, **kwargs)
            elif callable(self._task_executor) and asyncio.iscoroutinefunction(
                self._task_executor
            ):
                return await self._task_executor(input_data, **kwargs)
            else:
                # Fallback to sync run in thread pool
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, lambda: self.execute(input_data, **kwargs)
                )
        except Exception as exc:
            logger.exception(
                f"Async task execution failed for '{self.task_type}': {exc}"
            )
            raise FrameworkError(f"Async task execution failed: {exc}") from exc

    def list_available_tasks(self) -> Dict[str, Any]:
        """Get list of all available task types."""
        logger.debug("Listing all available task types.")
        registry = self._registry or self.get_registry()
        return {task_type: registry.get(task_type) for task_type in registry.list()}

    def get_task_schema(self, task_type: str) -> Dict[str, Any]:
        """Get input/output schema for a task type."""
        logger.debug(f"Getting schema for task_type='{task_type}'.")
        registry = self._registry or self.get_registry()
        definition = registry.get(task_type)
        if not definition:
            logger.error(f"Task type '{task_type}' is not registered.")
            raise TaskNotFoundError(f"Task type '{task_type}' is not registered.")
        # Try to get schema from the definition if available
        schema = {}
        if hasattr(definition, "input_schema"):
            schema["input"] = definition.input_schema
        if hasattr(definition, "output_schema"):
            schema["output"] = definition.output_schema
        return schema
