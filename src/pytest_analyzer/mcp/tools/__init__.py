"""MCP tools for pytest-analyzer.

Provides tool implementations following the MCP tools specification.
"""

from typing import Any

from ...core.infrastructure.base_factory import BaseFactory


class ToolFactory(BaseFactory):
    """Factory for creating MCP tool instances."""

    def create(self, tool_name: str, **kwargs) -> Any:
        """Create a tool instance by name.

        Args:
            tool_name: Name of the tool to create
            **kwargs: Additional tool configuration

        Returns:
            Instantiated tool

        Raises:
            KeyError: If tool_name not registered
        """
        tool_class = self.get_implementation(tool_name)
        return tool_class(**kwargs)


__all__ = ["ToolFactory"]
