"""
Protocol definitions for the LLM Task Framework.

This module defines the core protocol interfaces for the framework's
task execution system.
"""

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class TaskInput(Protocol):
    """Protocol for task input data."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert input to dictionary representation."""
        ...


@runtime_checkable
class TaskResult(Protocol):
    """Protocol for task execution results."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        ...


@runtime_checkable
class TaskExecutor(Protocol):
    """Protocol for executing tasks."""

    def execute(self, input_data: TaskInput) -> TaskResult:
        """Execute a task with the given input data."""
        ...

    async def execute_async(self, input_data: TaskInput) -> TaskResult:
        """Execute a task asynchronously with the given input data."""
        ...
