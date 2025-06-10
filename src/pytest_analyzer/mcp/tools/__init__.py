"""MCP tools for pytest-analyzer.

Provides tool implementations following the MCP tools specification.
"""

from typing import Any

from ...core.infrastructure.base_factory import BaseFactory
from .analysis import (
    RUN_AND_ANALYZE_TOOL_INFO,
    SUGGEST_FIXES_TOOL_INFO,
    run_and_analyze,
    suggest_fixes,
)
from .configuration import (
    UPDATE_CONFIG_TOOL_INFO,
    update_config,
)
from .fixes import (
    APPLY_SUGGESTION_TOOL_INFO,
    VALIDATE_SUGGESTION_TOOL_INFO,
    apply_suggestion,
    validate_suggestion,
)
from .information import (
    GET_FAILURE_SUMMARY_TOOL_INFO,
    GET_TEST_COVERAGE_TOOL_INFO,
    get_failure_summary,
    get_test_coverage,
)


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


# Available tools registry
AVAILABLE_TOOLS = {
    "suggest_fixes": SUGGEST_FIXES_TOOL_INFO,
    "run_and_analyze": RUN_AND_ANALYZE_TOOL_INFO,
    "apply_suggestion": APPLY_SUGGESTION_TOOL_INFO,
    "validate_suggestion": VALIDATE_SUGGESTION_TOOL_INFO,
    "get_failure_summary": GET_FAILURE_SUMMARY_TOOL_INFO,
    "get_test_coverage": GET_TEST_COVERAGE_TOOL_INFO,
    "update_config": UPDATE_CONFIG_TOOL_INFO,
}


__all__ = [
    "ToolFactory",
    "AVAILABLE_TOOLS",
    "suggest_fixes",
    "run_and_analyze",
    "apply_suggestion",
    "validate_suggestion",
    "get_failure_summary",
    "get_test_coverage",
    "update_config",
    "SUGGEST_FIXES_TOOL_INFO",
    "RUN_AND_ANALYZE_TOOL_INFO",
    "APPLY_SUGGESTION_TOOL_INFO",
    "VALIDATE_SUGGESTION_TOOL_INFO",
    "GET_FAILURE_SUMMARY_TOOL_INFO",
    "GET_TEST_COVERAGE_TOOL_INFO",
    "UPDATE_CONFIG_TOOL_INFO",
]
