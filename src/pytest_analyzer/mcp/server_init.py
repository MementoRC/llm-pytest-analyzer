"""MCP server initialization for pytest-analyzer.

This module registers all available MCP tools with the server at startup.
"""

from typing import Any, Awaitable, Callable, Dict

from .facade import MCPAnalyzerFacade
from .tools.analysis import (
    RUN_AND_ANALYZE_TOOL_INFO,
    SUGGEST_FIXES_TOOL_INFO,
    run_and_analyze,
    suggest_fixes,
)
from .tools.configuration import UPDATE_CONFIG_TOOL_INFO, update_config
from .tools.fixes import (
    APPLY_SUGGESTION_TOOL_INFO,
    VALIDATE_SUGGESTION_TOOL_INFO,
    apply_suggestion,
    validate_suggestion,
)
from .tools.information import (
    GET_FAILURE_SUMMARY_TOOL_INFO,
    GET_TEST_COVERAGE_TOOL_INFO,
    get_failure_summary,
    get_test_coverage,
)


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

    # Register all analysis tools
    server.register_tool(
        name=SUGGEST_FIXES_TOOL_INFO["name"],
        description=SUGGEST_FIXES_TOOL_INFO["description"],
        handler=make_tool_handler(suggest_fixes),
        input_schema=SUGGEST_FIXES_TOOL_INFO.get("input_schema"),
    )

    server.register_tool(
        name=RUN_AND_ANALYZE_TOOL_INFO["name"],
        description=RUN_AND_ANALYZE_TOOL_INFO["description"],
        handler=make_tool_handler(run_and_analyze),
        input_schema=RUN_AND_ANALYZE_TOOL_INFO.get("input_schema"),
    )

    # Register all fix application tools
    server.register_tool(
        name=APPLY_SUGGESTION_TOOL_INFO["name"],
        description=APPLY_SUGGESTION_TOOL_INFO["description"],
        handler=make_tool_handler(apply_suggestion),
        input_schema=APPLY_SUGGESTION_TOOL_INFO.get("input_schema"),
    )

    server.register_tool(
        name=VALIDATE_SUGGESTION_TOOL_INFO["name"],
        description=VALIDATE_SUGGESTION_TOOL_INFO["description"],
        handler=make_tool_handler(validate_suggestion),
        input_schema=VALIDATE_SUGGESTION_TOOL_INFO.get("input_schema"),
    )

    # Register all information tools
    server.register_tool(
        name=GET_FAILURE_SUMMARY_TOOL_INFO["name"],
        description=GET_FAILURE_SUMMARY_TOOL_INFO["description"],
        handler=make_tool_handler(get_failure_summary),
        input_schema=GET_FAILURE_SUMMARY_TOOL_INFO.get("input_schema"),
    )

    server.register_tool(
        name=GET_TEST_COVERAGE_TOOL_INFO["name"],
        description=GET_TEST_COVERAGE_TOOL_INFO["description"],
        handler=make_tool_handler(get_test_coverage),
        input_schema=GET_TEST_COVERAGE_TOOL_INFO.get("input_schema"),
    )

    # Register all configuration tools
    server.register_tool(
        name=UPDATE_CONFIG_TOOL_INFO["name"],
        description=UPDATE_CONFIG_TOOL_INFO["description"],
        handler=make_tool_handler(update_config),
        input_schema=UPDATE_CONFIG_TOOL_INFO.get("input_schema"),
    )
