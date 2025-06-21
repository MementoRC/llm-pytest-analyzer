#!/usr/bin/env python3
"""
Simplified MCP server for pytest-analyzer following aider's pattern.
This removes the complex wrapper classes and uses direct MCP server setup.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Configure logging
logger = logging.getLogger("pytest_analyzer.mcp.simple")

# Import the existing tools and tool info
try:
    from ..core.analyzer_facade import PytestAnalyzerFacade
    from ..utils.settings import Settings, load_settings

    # Import the facade for actual functionality
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

    TOOLS_AVAILABLE = True
    logger.info("All MCP tools imported successfully")

except ImportError as e:
    logger.error(f"Failed to import MCP tools: {e}")
    TOOLS_AVAILABLE = False


async def serve_simple_pytest_analyzer(
    project_root: Optional[str] = None, config_file: Optional[str] = None
) -> None:
    """Start a simple MCP server for pytest-analyzer over stdio."""
    logger.info("Starting Pytest Analyzer MCP Server (stdio mode, simplified)")

    if not TOOLS_AVAILABLE:
        logger.error("Cannot start server: MCP tools not available")
        sys.exit(1)

    # Initialize settings and facades
    try:
        settings = load_settings(config_file) if config_file else Settings()
        if project_root:
            settings.project_root = Path(project_root)

        core_facade = PytestAnalyzerFacade(settings=settings)
        mcp_facade = MCPAnalyzerFacade(core_facade)
        logger.info(f"Initialized with project root: {settings.project_root}")

    except Exception as e:
        logger.error(f"Failed to initialize facades: {e}")
        sys.exit(1)

    # Create the MCP server instance (exactly like aider)
    server: Server[List[TextContent]] = Server("pytest-analyzer")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        """List all available tools."""
        logger.info("Tools requested")

        # Create Tool objects from the tool info
        tools = []

        for tool_info in [
            SUGGEST_FIXES_TOOL_INFO,
            RUN_AND_ANALYZE_TOOL_INFO,
            APPLY_SUGGESTION_TOOL_INFO,
            VALIDATE_SUGGESTION_TOOL_INFO,
            GET_FAILURE_SUMMARY_TOOL_INFO,
            GET_TEST_COVERAGE_TOOL_INFO,
            UPDATE_CONFIG_TOOL_INFO,
        ]:
            tool = Tool(
                name=tool_info["name"],
                description=tool_info["description"],
                inputSchema=tool_info.get("input_schema", {}),
            )
            tools.append(tool)

        logger.info(f"Returning {len(tools)} tools")
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Handle tool calls."""
        logger.info(f"Tool called: {name}")

        try:
            # Route to appropriate handler using the actual tool functions
            if name == "suggest_fixes":
                result = await suggest_fixes(arguments, mcp_facade)
            elif name == "run_and_analyze":
                result = await run_and_analyze(arguments, mcp_facade)
            elif name == "apply_suggestion":
                result = await apply_suggestion(arguments, mcp_facade)
            elif name == "validate_suggestion":
                result = await validate_suggestion(arguments, mcp_facade)
            elif name == "get_failure_summary":
                result = await get_failure_summary(arguments, mcp_facade)
            elif name == "get_test_coverage":
                result = await get_test_coverage(arguments, mcp_facade)
            elif name == "update_config":
                result = await update_config(arguments, mcp_facade)
            else:
                error_msg = f"Unknown tool: {name}"
                logger.error(error_msg)
                return [TextContent(type="text", text=error_msg)]

            # The tool functions should return CallToolResult, extract the content
            if hasattr(result, "content"):
                return result.content
            elif isinstance(result, list):
                return result
            elif isinstance(result, dict):
                import json

                response_text = json.dumps(result, indent=2)
                return [TextContent(type="text", text=response_text)]
            else:
                response_text = str(result)
                return [TextContent(type="text", text=response_text)]

        except Exception as e:
            error_msg = f"Error executing tool {name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return [TextContent(type="text", text=error_msg)]

    # Initialize and run the server (exactly like aider)
    try:
        options = server.create_initialization_options()
        logger.info("Initializing stdio server connection...")
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server running. Waiting for requests...")
            await server.run(read_stream, write_stream, options, raise_exceptions=True)
    except Exception as e:
        logger.exception(
            f"Critical Error: Server stopped due to unhandled exception: {e}"
        )
        sys.exit(1)
    finally:
        logger.info("Pytest Analyzer MCP Server (stdio mode) shutting down.")


def main():
    """Main entry point for simplified server."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Simplified Pytest Analyzer MCP Server"
    )
    parser.add_argument("--project-root", help="Project root directory")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        asyncio.run(
            serve_simple_pytest_analyzer(
                project_root=args.project_root, config_file=args.config
            )
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
