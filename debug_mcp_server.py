#!/usr/bin/env python3
"""
Debug version of pytest-analyzer MCP server to identify where it hangs.
This adds extensive logging to track the exact point of failure.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Set up detailed logging immediately
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(
            sys.stderr
        ),  # Important: log to stderr so stdout is clean for MCP
        logging.FileHandler("/tmp/pytest_analyzer_debug.log"),
    ],
)

logger = logging.getLogger("debug_mcp")
logger.info("=== DEBUG MCP SERVER STARTING ===")

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    logger.info("✅ MCP imports successful")
except Exception as e:
    logger.error(f"❌ MCP imports failed: {e}")
    sys.exit(1)

try:
    from src.pytest_analyzer.core.analyzer_facade import PytestAnalyzerFacade
    from src.pytest_analyzer.mcp.facade import MCPAnalyzerFacade
    from src.pytest_analyzer.mcp.tools.analysis import (
        RUN_AND_ANALYZE_TOOL_INFO,
        SUGGEST_FIXES_TOOL_INFO,
        run_and_analyze,
        suggest_fixes,
    )
    from src.pytest_analyzer.utils.settings import Settings

    logger.info("✅ pytest-analyzer imports successful")
except Exception as e:
    logger.error(f"❌ pytest-analyzer imports failed: {e}")
    sys.exit(1)


async def debug_serve():
    """Debug version of the MCP server with extensive logging."""
    logger.info("=== STARTING DEBUG SERVE FUNCTION ===")

    try:
        # Initialize settings and facade
        logger.info("1. Creating settings...")
        start_time = time.time()
        settings = Settings()
        settings.project_root = Path(
            "/home/memento/ClaudeCode/pytest-analyzer/llm-pytest-analyzer"
        )
        logger.info(f"   Settings created in {time.time() - start_time:.3f}s")

        logger.info("2. Creating core facade...")
        start_time = time.time()
        core_facade = PytestAnalyzerFacade(settings=settings)
        logger.info(f"   Core facade created in {time.time() - start_time:.3f}s")

        logger.info("3. Creating MCP facade...")
        start_time = time.time()
        mcp_facade = MCPAnalyzerFacade(core_facade)
        logger.info(f"   MCP facade created in {time.time() - start_time:.3f}s")

        # Create MCP Server
        logger.info("4. Creating MCP Server...")
        start_time = time.time()
        server = Server("pytest-analyzer-debug")
        logger.info(f"   MCP Server created in {time.time() - start_time:.3f}s")

        # Register tools
        logger.info("5. Registering tools...")
        start_time = time.time()

        @server.list_tools()
        async def list_tools():
            logger.info("   🔧 list_tools() called")
            tools = [
                Tool(
                    name=SUGGEST_FIXES_TOOL_INFO["name"],
                    description=SUGGEST_FIXES_TOOL_INFO["description"],
                    inputSchema=SUGGEST_FIXES_TOOL_INFO.get("input_schema", {}),
                ),
                Tool(
                    name=RUN_AND_ANALYZE_TOOL_INFO["name"],
                    description=RUN_AND_ANALYZE_TOOL_INFO["description"],
                    inputSchema=RUN_AND_ANALYZE_TOOL_INFO.get("input_schema", {}),
                ),
            ]
            logger.info(f"   🔧 Returning {len(tools)} tools")
            return tools

        @server.call_tool()
        async def call_tool(name: str, arguments: dict):
            logger.info(f"   🛠️  call_tool() called: {name}")
            try:
                if name == "suggest_fixes":
                    result = await suggest_fixes(arguments, mcp_facade)
                elif name == "run_and_analyze":
                    result = await run_and_analyze(arguments, mcp_facade)
                else:
                    error_msg = f"Unknown tool: {name}"
                    logger.error(f"   ❌ {error_msg}")
                    return [TextContent(type="text", text=error_msg)]

                if hasattr(result, "content"):
                    return result.content
                else:
                    return [TextContent(type="text", text=str(result))]
            except Exception as e:
                error_msg = f"Error in tool {name}: {e}"
                logger.error(f"   ❌ {error_msg}", exc_info=True)
                return [TextContent(type="text", text=error_msg)]

        logger.info(f"   Tools registered in {time.time() - start_time:.3f}s")

        # Start stdio server
        logger.info("6. Creating initialization options...")
        start_time = time.time()
        options = server.create_initialization_options()
        logger.info(f"   Options created in {time.time() - start_time:.3f}s")

        logger.info("7. Starting stdio_server context...")
        start_time = time.time()

        # Debug the stdio streams
        logger.info("   Checking stdin/stdout state...")
        logger.info(f"   stdin.isatty(): {sys.stdin.isatty()}")
        logger.info(f"   stdout.isatty(): {sys.stdout.isatty()}")
        logger.info(f"   stderr.isatty(): {sys.stderr.isatty()}")

        async with stdio_server() as (read_stream, write_stream):
            logger.info(
                f"   stdio_server context entered in {time.time() - start_time:.3f}s"
            )
            logger.info(f"   read_stream: {read_stream}")
            logger.info(f"   write_stream: {write_stream}")

            logger.info("8. Starting server.run()...")
            start_time = time.time()
            logger.info(
                "   📡 MCP Server ready for connections - about to call server.run()"
            )

            # Remove the timeout - let it run and see what happens
            await server.run(read_stream, write_stream, options, raise_exceptions=True)

            logger.info(f"   server.run() completed in {time.time() - start_time:.3f}s")

    except Exception as e:
        logger.error(f"❌ CRITICAL ERROR in debug_serve: {e}", exc_info=True)
        raise


def main():
    """Main entry point."""
    logger.info("=== DEBUG MCP MAIN STARTING ===")

    # Add project root to Python path
    sys.path.insert(0, "/home/memento/ClaudeCode/pytest-analyzer/llm-pytest-analyzer")

    try:
        asyncio.run(debug_serve())
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ FATAL ERROR: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("=== DEBUG MCP SERVER SHUTDOWN ===")


if __name__ == "__main__":
    main()
