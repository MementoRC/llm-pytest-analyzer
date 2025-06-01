"""MCP resource handlers for pytest-analyzer.

Provides resource management for MCP operations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class ResourceHandler(ABC):
    """Base class for MCP resource handlers."""

    @abstractmethod
    async def handle(self, resource_id: str, **kwargs) -> Dict[str, Any]:
        """Handle resource request.

        Args:
            resource_id: Resource identifier
            **kwargs: Additional parameters

        Returns:
            Resource response dictionary
        """
        pass


__all__ = ["ResourceHandler"]
