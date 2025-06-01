"""MCP schema definitions for pytest-analyzer.

Defines the JSON schemas for MCP request/response validation.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class MCPSchema:
    """Base class for MCP schemas."""

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert schema to dictionary format."""
        raise NotImplementedError


__all__ = ["MCPSchema"]
