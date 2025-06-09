"""MCP server initialization for pytest-analyzer.

This module registers all available MCP tools with the server at startup.
"""

from typing import Any, Awaitable, Callable, Dict

from .facade import MCPAnalyzerFacade
from .tools.analysis import SUGGEST_FIXES_TOOL_INFO, suggest_fixes


def register_all_tools(server, facade: MCPAnalyzerFacade) -> None:
    """
    Register all available MCP tools with the server.

    Args:
        server: PytestAnalyzerMCPServer instance
        facade: MCPAnalyzerFacade instance
    """

    # Wrapper to inject facade into tool handler
    def make_tool_handler(
        tool_func: Callable[[Dict[str, Any], MCPAnalyzerFacade], Awaitable[Any]],
    ) -> Callable[[Dict[str, Any]], Awaitable[Any]]:
        async def handler(arguments: Dict[str, Any]) -> Any:
            return await tool_func(arguments, facade)

        return handler

    # Register suggest_fixes tool
    server.register_tool(
        name=SUGGEST_FIXES_TOOL_INFO["name"],
        description=SUGGEST_FIXES_TOOL_INFO["description"],
        handler=make_tool_handler(suggest_fixes),
        input_schema=SUGGEST_FIXES_TOOL_INFO.get("input_schema"),
    )
