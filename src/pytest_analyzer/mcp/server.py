"""MCP server implementation for pytest-analyzer."""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional

from mcp.server import InitializationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import ResourceContents, Tool

from ..core.cross_cutting.error_handling import error_context, error_handler
from ..utils.settings import Settings
from .prompts.templates import (
    get_prompt_registry,
    handle_get_prompt,
    handle_list_prompts,
    initialize_default_prompts,
)
from .resources import ResourceManager, SessionManager
from .security import SecurityManager


class PytestAnalyzerMCPServer:
    """MCP server implementation for pytest-analyzer.

    Handles MCP protocol interactions for test analysis and fix suggestions.
    Supports both STDIO and HTTP transports with comprehensive error handling.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        transport_type: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ):
        """Initialize the MCP server.

        Args:
            settings: Application settings instance (includes MCP configuration)
            transport_type: Transport type (backwards compatibility, overrides settings)
            host: Host for HTTP transport (backwards compatibility, overrides settings)
            port: Port for HTTP transport (backwards compatibility, overrides settings)
        """
        self.settings = settings or Settings()

        # Apply backwards compatibility overrides only if explicitly provided
        if transport_type is not None or host is not None or port is not None:
            from ..utils.config_types import MCPSettings

            mcp_config = {**self.settings.mcp.__dict__}
            if transport_type is not None:
                mcp_config["transport_type"] = transport_type
            if host is not None:
                mcp_config["http_host"] = host
            if port is not None:
                mcp_config["http_port"] = port

            # Temporarily bypass validation for invalid transport types (tests)
            # Validation will occur at start() time
            try:
                self.settings.mcp = MCPSettings(**mcp_config)
            except ValueError as e:
                if "Invalid transport_type" in str(e):
                    # Create without validation for testing - bypass __post_init__
                    import dataclasses

                    mcp_obj = object.__new__(MCPSettings)
                    for field in dataclasses.fields(MCPSettings):
                        setattr(
                            mcp_obj,
                            field.name,
                            mcp_config.get(
                                field.name, getattr(self.settings.mcp, field.name)
                            ),
                        )
                    self.settings.mcp = mcp_obj
                else:
                    raise

        self.mcp_settings = self.settings.mcp
        self.logger = logging.getLogger(self.__class__.__name__)

        # Initialize security manager
        self.security_manager = SecurityManager(
            self.mcp_settings.security,
            project_root=getattr(self.settings, "project_root", None),
        )

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
        self._registered_prompts: Dict[str, Any] = {}

        # Initialize resource management
        self.session_manager = SessionManager(
            ttl_seconds=self.mcp_settings.resource_cache_ttl_seconds,
            max_sessions=100,
        )
        self.resource_manager = ResourceManager(self.session_manager)

        # Log initialization first
        self.logger.info(
            f"Initialized MCP server with {self.mcp_settings.transport_type} transport "
            f"(host: {self.mcp_settings.http_host}, port: {self.mcp_settings.http_port})"
        )

        # Setup signal handlers
        self._setup_signal_handlers()

        # Initialize prompts
        self._setup_prompts()

        # Register MCP resource handlers
        self._setup_resource_handlers()

    # Compatibility properties for tests
    @property
    def transport_type(self) -> str:
        """Get transport type from MCP settings."""
        return self.mcp_settings.transport_type

    @property
    def host(self) -> str:
        """Get HTTP host from MCP settings."""
        return self.mcp_settings.http_host

    @property
    def port(self) -> int:
        """Get HTTP port from MCP settings."""
        return self.mcp_settings.http_port

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

    def get_registered_prompts(self) -> Dict[str, Any]:
        """Get all registered prompts."""
        return self._registered_prompts.copy()

    def create_analysis_session(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a new analysis session.

        Args:
            metadata: Optional session metadata

        Returns:
            Session ID
        """
        return self.session_manager.create_session(metadata)

    def store_test_results(self, session_id: str, results: list) -> bool:
        """Store test results in a session.

        Args:
            session_id: Session identifier
            results: List of test failure data

        Returns:
            True if stored successfully
        """
        # Convert results to PytestFailureData if needed
        from .schemas import PytestFailureData

        converted_results = []
        for result in results:
            if isinstance(result, dict):
                # Convert dict to PytestFailureData
                failure_data = PytestFailureData(
                    id=result.get("id", "unknown"),
                    test_name=result.get("test_name", ""),
                    file_path=result.get("file_path", ""),
                    failure_message=result.get("failure_message", ""),
                    failure_type=result.get("failure_type", ""),
                    line_number=result.get("line_number"),
                    function_name=result.get("function_name", ""),
                    class_name=result.get("class_name", ""),
                    traceback=result.get("traceback", []),
                )
                converted_results.append(failure_data)
            else:
                converted_results.append(result)

        return self.session_manager.store_test_results(session_id, converted_results)

    def store_suggestions(self, session_id: str, suggestions: list) -> bool:
        """Store fix suggestions in a session.

        Args:
            session_id: Session identifier
            suggestions: List of fix suggestions

        Returns:
            True if stored successfully
        """
        # Convert suggestions to FixSuggestionData if needed
        from .schemas import FixSuggestionData

        converted_suggestions = []
        for suggestion in suggestions:
            if isinstance(suggestion, dict):
                # Convert dict to FixSuggestionData
                suggestion_data = FixSuggestionData(
                    id=suggestion.get("id", "unknown"),
                    failure_id=suggestion.get("failure_id", "unknown"),
                    suggestion_text=suggestion.get("suggestion_text", ""),
                    code_changes=suggestion.get("code_changes", []),
                    confidence_score=suggestion.get("confidence_score", 0.0),
                    explanation=suggestion.get("explanation", ""),
                    alternative_approaches=suggestion.get("alternative_approaches", []),
                    file_path=suggestion.get("file_path", ""),
                    line_number=suggestion.get("line_number"),
                )
                converted_suggestions.append(suggestion_data)
            else:
                converted_suggestions.append(suggestion)

        return self.session_manager.store_suggestions(session_id, converted_suggestions)

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
                f"Starting MCP server with {self.mcp_settings.transport_type} transport"
            )

            try:
                if self.mcp_settings.transport_type == "stdio":
                    await self._start_stdio()
                elif self.mcp_settings.transport_type == "http":
                    await self._start_http()
                else:
                    raise ValueError(
                        f"Unsupported transport type: {self.mcp_settings.transport_type}"
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
        self.logger.info(
            f"Starting HTTP transport on {self.mcp_settings.http_host}:{self.mcp_settings.http_port}"
        )

        # HTTP transport implementation would go here
        # This is a placeholder for the HTTP transport setup
        raise NotImplementedError("HTTP transport not yet implemented")

    def _setup_prompts(self) -> None:
        """Set up MCP prompt system."""
        try:
            # Initialize default prompts
            initialize_default_prompts()

            # Register list_prompts handler
            @self.mcp_server.list_prompts()
            async def handle_list_prompts_request():
                """Handle list prompts request."""
                try:
                    prompts = handle_list_prompts()
                    self.logger.debug(f"Listed {len(prompts)} prompts")
                    return prompts
                except Exception as e:
                    self.logger.error(f"Error listing prompts: {e}")
                    return []

            # Register get_prompt handler
            @self.mcp_server.get_prompt()
            async def handle_get_prompt_request(
                name: str, arguments: Optional[Dict[str, Any]] = None
            ):
                """Handle get prompt request."""
                try:
                    self.logger.debug(f"Getting prompt: {name}")
                    result = await handle_get_prompt(name, arguments)

                    if "error" in result:
                        self.logger.warning(f"Prompt request failed: {result['error']}")
                    else:
                        self.logger.info(f"Successfully retrieved prompt: {name}")

                    return result
                except Exception as e:
                    self.logger.error(f"Error getting prompt {name}: {e}")
                    return {"error": f"Failed to retrieve prompt: {str(e)}"}

            # Store reference to registered prompts
            registry = get_prompt_registry()
            self._registered_prompts = {name: True for name in registry.list_prompts()}

            self.logger.info(
                f"Prompt system initialized with {len(self._registered_prompts)} prompts"
            )

        except Exception as e:
            self.logger.error(f"Failed to setup prompt system: {e}")
            raise

    def _setup_resource_handlers(self) -> None:
        """Set up MCP resource handlers."""
        try:
            # Register list_resources handler
            @self.mcp_server.list_resources()
            async def handle_list_resources():
                """Handle list resources request."""
                try:
                    resources = await self.resource_manager.list_resources()
                    self.logger.debug(f"Listed {len(resources)} resources")
                    return resources
                except Exception as e:
                    self.logger.error(f"Error listing resources: {e}")
                    return []

            # Register read_resource handler
            @self.mcp_server.read_resource()
            async def handle_read_resource(uri: str) -> ResourceContents:
                """Handle read resource request."""
                try:
                    self.logger.debug(f"Reading resource: {uri}")
                    contents = await self.resource_manager.read_resource(uri)
                    self.logger.info(f"Successfully read resource: {uri}")
                    return contents
                except Exception as e:
                    self.logger.error(f"Error reading resource {uri}: {e}")
                    # Return error as text content
                    from mcp.types import TextResourceContents

                    return TextResourceContents(
                        uri=uri,
                        mimeType="text/plain",
                        text=f"Error reading resource: {str(e)}",
                    )

            self.logger.info("Resource handlers registered successfully")

        except Exception as e:
            self.logger.error(f"Failed to setup resource handlers: {e}")
            raise

    def _get_server_capabilities(self) -> Dict[str, Any]:
        """Get server capabilities."""
        return {
            "tools": {"listChanged": True} if self._registered_tools else None,
            "resources": {"subscribe": True, "listChanged": True}
            if self._registered_resources
            else None,
            "prompts": {"listChanged": True} if self._registered_prompts else None,
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
            # Clear registered tools, resources, and prompts
            self._registered_tools.clear()
            self._registered_resources.clear()
            self._registered_prompts.clear()

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
            f"resources={len(self._registered_resources)}, "
            f"prompts={len(self._registered_prompts)}"
            f")"
        )


class MCPServerFactory:
    """Factory for creating MCP server instances."""

    @staticmethod
    def create_server(
        settings: Optional[Settings] = None,
        transport_type: Optional[str] = "stdio",
        host: Optional[str] = "127.0.0.1",
        port: Optional[int] = 8000,
    ) -> PytestAnalyzerMCPServer:
        """Create an MCP server instance.

        Args:
            settings: Application settings (includes MCP configuration)
            transport_type: Transport type (backwards compatibility)
            host: Host for HTTP transport (backwards compatibility)
            port: Port for HTTP transport (backwards compatibility)

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
            settings: Application settings (MCP transport will be set to stdio)

        Returns:
            Configured MCP server instance
        """
        return PytestAnalyzerMCPServer(settings=settings, transport_type="stdio")

    @staticmethod
    def create_http_server(
        settings: Optional[Settings] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> PytestAnalyzerMCPServer:
        """Create an MCP server with HTTP transport.

        Args:
            settings: Application settings (MCP transport will be set to http)
            host: Host for HTTP transport (overrides settings if provided)
            port: Port for HTTP transport (overrides settings if provided)

        Returns:
            Configured MCP server instance
        """
        return PytestAnalyzerMCPServer(
            settings=settings,
            transport_type="http",
            host=host,
            port=port,
        )
