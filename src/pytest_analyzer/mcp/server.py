"""MCP server implementation for pytest-analyzer."""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional

from mcp.server import InitializationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from ..core.cross_cutting.error_handling import error_context, error_handler
from ..utils.settings import Settings


class PytestAnalyzerMCPServer:
    """MCP server implementation for pytest-analyzer.

    Handles MCP protocol interactions for test analysis and fix suggestions.
    Supports both STDIO and HTTP transports with comprehensive error handling.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        transport_type: str = "stdio",
        host: str = "127.0.0.1",
        port: int = 8000,
    ):
        """Initialize the MCP server.

        Args:
            settings: Application settings instance
            transport_type: Transport type ("stdio" or "http")
            host: Host for HTTP transport
            port: Port for HTTP transport
        """
        self.settings = settings or Settings()
        self.transport_type = transport_type
        self.host = host
        self.port = port
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize MCP server with proper configuration
        self.mcp_server = Server(
            name="pytest-analyzer",
            version="1.0.0",
            instructions="MCP server for pytest test analysis and fix suggestions",
        )

        # Server state
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._registered_tools: Dict[str, Tool] = {}
        self._registered_resources: Dict[str, Any] = {}

        # Setup signal handlers
        self._setup_signal_handlers()

        self.logger.info(f"Initialized MCP server with {transport_type} transport")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
        asyncio.create_task(self.stop())

    @error_handler("tool_registration", ValueError, reraise=True)
    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        input_schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a tool with the MCP server.

        Args:
            name: Tool name
            description: Tool description
            handler: Tool handler function
            input_schema: Input schema for the tool

        Raises:
            ValueError: If tool name already exists or invalid parameters
        """
        if name in self._registered_tools:
            raise ValueError(f"Tool '{name}' already registered")

        with error_context("tool_registration", self.logger, ValueError):
            tool = Tool(
                name=name,
                description=description,
                inputSchema=input_schema or {"type": "object", "properties": {}},
            )

            # Register with MCP server
            self.mcp_server.list_tools()(lambda: [tool])
            self.mcp_server.call_tool()(handler)

            self._registered_tools[name] = tool
            self.logger.info(f"Registered tool: {name}")

    @error_handler("resource_registration", ValueError, reraise=True)
    def register_resource(
        self,
        uri: str,
        name: str,
        description: str,
        mime_type: str = "text/plain",
    ) -> None:
        """Register a resource with the MCP server.

        Args:
            uri: Resource URI
            name: Resource name
            description: Resource description
            mime_type: MIME type of the resource

        Raises:
            ValueError: If resource URI already exists
        """
        if uri in self._registered_resources:
            raise ValueError(f"Resource '{uri}' already registered")

        with error_context("resource_registration", self.logger, ValueError):
            resource_info = {
                "uri": uri,
                "name": name,
                "description": description,
                "mimeType": mime_type,
            }

            self._registered_resources[uri] = resource_info
            self.logger.info(f"Registered resource: {uri}")

    def get_registered_tools(self) -> Dict[str, Tool]:
        """Get all registered tools."""
        return self._registered_tools.copy()

    def get_registered_resources(self) -> Dict[str, Any]:
        """Get all registered resources."""
        return self._registered_resources.copy()

    @asynccontextmanager
    async def lifespan(self):
        """Async context manager for server lifespan."""
        try:
            self.logger.info("Starting MCP server lifespan")
            yield self
        except Exception as e:
            self.logger.error(f"Error during server lifespan: {e}")
            raise
        finally:
            self.logger.info("Ending MCP server lifespan")

    async def start(self) -> None:
        """Start the MCP server.

        Raises:
            RuntimeError: If server is already running
            ValueError: If invalid transport configuration
        """
        if self._running:
            raise RuntimeError("Server is already running")

        with error_context("server_startup", self.logger, RuntimeError):
            self.logger.info(
                f"Starting MCP server with {self.transport_type} transport"
            )

            try:
                if self.transport_type == "stdio":
                    await self._start_stdio()
                elif self.transport_type == "http":
                    await self._start_http()
                else:
                    raise ValueError(
                        f"Unsupported transport type: {self.transport_type}"
                    )

                self._running = True
                self.logger.info("MCP server started successfully")

            except Exception as e:
                self.logger.error(f"Failed to start MCP server: {e}")
                raise

    async def _start_stdio(self) -> None:
        """Start server with STDIO transport."""
        self.logger.info("Starting STDIO transport")

        try:
            async with stdio_server() as (read_stream, write_stream):
                await self.mcp_server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="pytest-analyzer",
                        server_version="1.0.0",
                        capabilities=self._get_server_capabilities(),
                    ),
                )
        except Exception as e:
            self.logger.error(f"STDIO transport error: {e}")
            raise

    async def _start_http(self) -> None:
        """Start server with HTTP transport."""
        self.logger.info(f"Starting HTTP transport on {self.host}:{self.port}")

        # HTTP transport implementation would go here
        # This is a placeholder for the HTTP transport setup
        raise NotImplementedError("HTTP transport not yet implemented")

    def _get_server_capabilities(self) -> Dict[str, Any]:
        """Get server capabilities."""
        return {
            "tools": {"listChanged": True} if self._registered_tools else None,
            "resources": {"subscribe": True, "listChanged": True}
            if self._registered_resources
            else None,
        }

    async def stop(self) -> None:
        """Stop the MCP server gracefully."""
        if not self._running:
            self.logger.warning("Server is not running")
            return

        with error_context("server_shutdown", self.logger, RuntimeError):
            self.logger.info("Stopping MCP server")

            try:
                # Signal shutdown
                self._shutdown_event.set()
                self._running = False

                # Cleanup resources
                await self._cleanup()

                self.logger.info("MCP server stopped successfully")

            except Exception as e:
                self.logger.error(f"Error during server shutdown: {e}")
                raise

    async def _cleanup(self) -> None:
        """Cleanup server resources."""
        try:
            # Clear registered tools and resources
            self._registered_tools.clear()
            self._registered_resources.clear()

            self.logger.info("Server cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            raise

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    def __str__(self) -> str:
        """String representation of the server."""
        return f"PytestAnalyzerMCPServer(transport={self.transport_type}, running={self._running})"

    def __repr__(self) -> str:
        """Detailed string representation of the server."""
        return (
            f"PytestAnalyzerMCPServer("
            f"transport_type='{self.transport_type}', "
            f"host='{self.host}', "
            f"port={self.port}, "
            f"running={self._running}, "
            f"tools={len(self._registered_tools)}, "
            f"resources={len(self._registered_resources)}"
            f")"
        )


class MCPServerFactory:
    """Factory for creating MCP server instances."""

    @staticmethod
    def create_server(
        settings: Optional[Settings] = None,
        transport_type: str = "stdio",
        host: str = "127.0.0.1",
        port: int = 8000,
    ) -> PytestAnalyzerMCPServer:
        """Create an MCP server instance.

        Args:
            settings: Application settings
            transport_type: Transport type ("stdio" or "http")
            host: Host for HTTP transport
            port: Port for HTTP transport

        Returns:
            Configured MCP server instance
        """
        return PytestAnalyzerMCPServer(
            settings=settings,
            transport_type=transport_type,
            host=host,
            port=port,
        )

    @staticmethod
    def create_stdio_server(
        settings: Optional[Settings] = None,
    ) -> PytestAnalyzerMCPServer:
        """Create an MCP server with STDIO transport.

        Args:
            settings: Application settings

        Returns:
            Configured MCP server instance
        """
        return MCPServerFactory.create_server(settings=settings, transport_type="stdio")

    @staticmethod
    def create_http_server(
        settings: Optional[Settings] = None,
        host: str = "127.0.0.1",
        port: int = 8000,
    ) -> PytestAnalyzerMCPServer:
        """Create an MCP server with HTTP transport.

        Args:
            settings: Application settings
            host: Host for HTTP transport
            port: Port for HTTP transport

        Returns:
            Configured MCP server instance
        """
        return MCPServerFactory.create_server(
            settings=settings,
            transport_type="http",
            host=host,
            port=port,
        )
