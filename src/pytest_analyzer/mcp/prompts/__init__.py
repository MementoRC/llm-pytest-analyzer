"""MCP prompt templates for pytest-analyzer.

Provides structured prompts for MCP interactions.
"""

from dataclasses import dataclass


@dataclass
class MCPPromptTemplate:
    """Base class for MCP prompt templates."""

    template: str

    def format(self, **kwargs) -> str:
        """Format prompt template with parameters.

        Args:
            **kwargs: Template parameters

        Returns:
            Formatted prompt string
        """
        return self.template.format(**kwargs)


__all__ = ["MCPPromptTemplate"]
