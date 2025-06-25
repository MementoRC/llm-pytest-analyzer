#!/usr/bin/env python3
"""
Simple MCP server test following aider's pattern exactly.
This is to test if the issue is in the server structure.
"""

import asyncio
import logging
import sys
from typing import Any, Dict, List

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Configure logging
logger = logging.getLogger("simple_mcp_test")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(levelname)s - %(name)s - %(message)s"))
logger.addHandler(handler)

# Define a simple tool following aider's pattern
SIMPLE_TEST_TOOL = Tool(
    name="simple_test",
    description="A simple test tool",
    inputSchema={
        "type": "object",
        "properties": {"message": {"type": "string", "description": "A test message"}},
        "required": ["message"],
    },
)


async def serve_simple() -> None:
    """Start a simple MCP server over stdio (following aider's exact pattern)."""
    logger.info("Starting Simple MCP Server (stdio mode)")

    # Create the MCP server instance for stdio (exactly like aider)
    server: Server[List[TextContent]] = Server("simple-mcp-test")

    @server.list_tools()
    async def list_tools() -> List[Tool]:
        logger.info("Tools requested")
        return [SIMPLE_TEST_TOOL]

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        logger.info(f"Tool called: {name}")
        if name == "simple_test":
            message = arguments.get("message", "No message")
            response = f"Test response: {message}"
            return [TextContent(type="text", text=response)]
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

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
        logger.info("Simple MCP Server (stdio mode) shutting down.")


def main():
    """Main entry point."""
    try:
        asyncio.run(serve_simple())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.exception(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
