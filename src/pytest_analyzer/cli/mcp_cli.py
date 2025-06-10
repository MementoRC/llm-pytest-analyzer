#!/usr/bin/env python3

"""
MCP server command-line interface for the pytest analyzer tool.

This module provides CLI commands for starting and managing the MCP server
for AI assistant integration.
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from rich.console import Console

from ..mcp.server import MCPServerFactory, PytestAnalyzerMCPServer
from ..utils.settings import Settings, load_settings

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv not available, continue without it
    pass

# Setup rich console
console = Console()

# Configure logging
logger = logging.getLogger("pytest_analyzer.mcp")


def setup_mcp_parser(subparsers) -> None:
    """Set up MCP server subcommand parsers."""

    # Main MCP command group
    mcp_parser = subparsers.add_parser(
        "mcp",
        help="MCP server management commands",
        description="Start and manage the MCP server for AI assistant integration",
    )

    # MCP subcommands
    mcp_subparsers = mcp_parser.add_subparsers(
        dest="mcp_command", help="MCP server commands", metavar="COMMAND"
    )

    # Start server command
    start_parser = mcp_subparsers.add_parser(
        "start",
        help="Start the MCP server",
        description="Start the MCP server with specified transport and configuration",
    )

    # Transport options (mutually exclusive)
    transport_group = start_parser.add_mutually_exclusive_group()
    transport_group.add_argument(
        "--stdio",
        action="store_true",
        help="Use STDIO transport (default for AI assistants)",
    )
    transport_group.add_argument(
        "--http",
        action="store_true",
        help="Use HTTP transport (for web-based integrations)",
    )

    # HTTP transport options
    start_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host for HTTP transport (default: 127.0.0.1)",
    )
    start_parser.add_argument(
        "--port", type=int, default=8000, help="Port for HTTP transport (default: 8000)"
    )

    # Configuration options
    start_parser.add_argument("--config", type=str, help="Path to configuration file")
    start_parser.add_argument(
        "--project-root",
        type=str,
        help="Root directory of the project (auto-detected if not specified)",
    )

    # Output control
    start_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    start_parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging"
    )
    start_parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress non-essential output"
    )

    # Set the handler function
    start_parser.set_defaults(func=cmd_start_server)


def configure_mcp_settings(args: argparse.Namespace) -> Settings:
    """Configure settings for MCP server based on command-line arguments."""

    # Load base settings from config file if provided
    settings = (
        load_settings(args.config)
        if hasattr(args, "config") and args.config
        else Settings()
    )

    # Update settings from command-line arguments
    if hasattr(args, "project_root") and args.project_root:
        settings.project_root = Path(args.project_root)

    # Configure logging level
    if hasattr(args, "debug") and args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("pytest_analyzer").setLevel(logging.DEBUG)
        settings.debug = True
    elif hasattr(args, "verbose") and args.verbose:
        logging.getLogger().setLevel(logging.INFO)
        logging.getLogger("pytest_analyzer").setLevel(logging.INFO)
    elif hasattr(args, "quiet") and args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("pytest_analyzer").setLevel(logging.WARNING)

    return settings


def determine_transport_type(args: argparse.Namespace) -> str:
    """Determine the transport type from command-line arguments."""
    if hasattr(args, "http") and args.http:
        return "http"
    elif hasattr(args, "stdio") and args.stdio:
        return "stdio"
    else:
        # Default to STDIO for AI assistant compatibility
        return "stdio"


async def start_mcp_server(
    settings: Settings,
    transport_type: str,
    host: str = "127.0.0.1",
    port: int = 8000,
    quiet: bool = False,
) -> None:
    """Start the MCP server with the specified configuration."""

    try:
        # Create server instance
        server: PytestAnalyzerMCPServer
        if transport_type == "stdio":
            server = MCPServerFactory.create_stdio_server(settings)
        else:  # http
            server = MCPServerFactory.create_http_server(
                settings=settings, host=host, port=port
            )

        # Create core analyzer facade and then MCP wrapper
        from ..core.analyzer_facade import PytestAnalyzerFacade
        from ..mcp.facade import MCPAnalyzerFacade
        from ..mcp.server_init import register_all_tools

        core_facade = PytestAnalyzerFacade(settings=settings)
        mcp_facade = MCPAnalyzerFacade(core_facade)
        register_all_tools(server, mcp_facade)

        if not quiet:
            transport_info = transport_type.upper()
            if transport_type == "http":
                transport_info += f" on {host}:{port}"

            console.print(
                f"[bold green]Starting MCP server with {transport_info} transport...[/bold green]"
            )
            console.print(f"[dim]Server configuration: {server}[/dim]")

        # Setup signal handlers for graceful shutdown
        shutdown_event = asyncio.Event()

        def signal_handler():
            if not quiet:
                console.print(
                    "\n[yellow]Shutdown signal received, stopping server...[/yellow]"
                )
            shutdown_event.set()

        # Register signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(sig, signal_handler)

        # Start server
        async with server.lifespan():
            if not quiet:
                console.print(
                    "[bold green]MCP server started successfully![/bold green]"
                )
                console.print("[dim]Press Ctrl+C to stop the server[/dim]")

            # Keep the server running until shutdown signal
            await shutdown_event.wait()

        if not quiet:
            console.print("[bold green]MCP server stopped successfully.[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Failed to start MCP server: {e}[/bold red]")
        logger.error(f"MCP server startup failed: {e}")
        raise


def cmd_start_server(args: argparse.Namespace) -> int:
    """Command handler for starting the MCP server."""

    try:
        # Configure settings
        settings = configure_mcp_settings(args)

        # Determine transport configuration
        transport_type = determine_transport_type(args)
        host = getattr(args, "host", "127.0.0.1")
        port = getattr(args, "port", 8000)
        quiet = getattr(args, "quiet", False)

        # Validate configuration
        if transport_type == "http" and (port < 1 or port > 65535):
            console.print(
                f"[bold red]Error: Invalid port number {port}. Must be between 1 and 65535.[/bold red]"
            )
            return 1

        # Run the server
        asyncio.run(
            start_mcp_server(
                settings=settings,
                transport_type=transport_type,
                host=host,
                port=port,
                quiet=quiet,
            )
        )

        return 0

    except KeyboardInterrupt:
        if not getattr(args, "quiet", False):
            console.print("\n[yellow]Server stopped by user.[/yellow]")
        return 0
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        if getattr(args, "debug", False):
            logger.exception("Detailed error information:")
        return 1


def main() -> int:
    """Main entry point for MCP CLI (for standalone usage)."""

    parser = argparse.ArgumentParser(
        description="MCP server for pytest-analyzer AI assistant integration",
        prog="pytest-analyzer-mcp",
    )

    # Add global options
    parser.add_argument(
        "--version", action="version", version="pytest-analyzer MCP server 1.0.0"
    )

    # Create subparsers for MCP commands
    subparsers = parser.add_subparsers(
        dest="command", help="Available commands", metavar="COMMAND"
    )

    # Setup MCP commands (reusing the function from main CLI)
    setup_mcp_parser(subparsers)

    # Parse arguments
    args = parser.parse_args()

    # Handle no command specified
    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    # Execute the command
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
