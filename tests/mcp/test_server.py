"""Tests for MCP server implementation."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pytest_analyzer.mcp.server import MCPServerFactory, PytestAnalyzerMCPServer
from pytest_analyzer.utils.settings import Settings


class TestPytestAnalyzerMCPServer:
    """Test cases for PytestAnalyzerMCPServer."""

    def test_init_default_settings(self):
        """Test server initialization with default settings."""
        server = PytestAnalyzerMCPServer()

        assert server.transport_type == "stdio"
        assert server.host == "127.0.0.1"
        assert server.port == 8000
        assert server.settings is not None
        assert not server.is_running
        assert len(server.get_registered_tools()) == 0
        assert len(server.get_registered_resources()) == 0

    def test_init_custom_settings(self):
        """Test server initialization with custom settings."""
        settings = Settings()
        server = PytestAnalyzerMCPServer(
            settings=settings, transport_type="http", host="0.0.0.0", port=9000
        )

        assert server.settings is settings
        assert server.transport_type == "http"
        assert server.host == "0.0.0.0"
        assert server.port == 9000

    def test_register_tool_success(self):
        """Test successful tool registration."""
        server = PytestAnalyzerMCPServer()

        def dummy_handler():
            return "test"

        with (
            patch.object(server.mcp_server, "list_tools") as mock_list,
            patch.object(server.mcp_server, "call_tool") as mock_call,
        ):
            mock_list.return_value = MagicMock()
            mock_call.return_value = MagicMock()

            server.register_tool(
                name="test_tool",
                description="Test tool",
                handler=dummy_handler,
                input_schema={"type": "object"},
            )

            tools = server.get_registered_tools()
            assert "test_tool" in tools
            assert tools["test_tool"].name == "test_tool"
            assert tools["test_tool"].description == "Test tool"

    def test_register_tool_duplicate_name(self):
        """Test tool registration with duplicate name raises error."""
        server = PytestAnalyzerMCPServer()

        def dummy_handler():
            return "test"

        with (
            patch.object(server.mcp_server, "list_tools") as mock_list,
            patch.object(server.mcp_server, "call_tool") as mock_call,
        ):
            mock_list.return_value = MagicMock()
            mock_call.return_value = MagicMock()

            # Register first tool
            server.register_tool("test_tool", "Test tool", dummy_handler)

            # Try to register duplicate
            with pytest.raises(ValueError, match="already registered"):
                server.register_tool("test_tool", "Another tool", dummy_handler)

    def test_register_resource_success(self):
        """Test successful resource registration."""
        server = PytestAnalyzerMCPServer()

        server.register_resource(
            uri="test://resource",
            name="Test Resource",
            description="A test resource",
            mime_type="application/json",
        )

        resources = server.get_registered_resources()
        assert "test://resource" in resources
        resource = resources["test://resource"]
        assert resource["name"] == "Test Resource"
        assert resource["description"] == "A test resource"
        assert resource["mimeType"] == "application/json"

    def test_register_resource_duplicate_uri(self):
        """Test resource registration with duplicate URI raises error."""
        server = PytestAnalyzerMCPServer()

        # Register first resource
        server.register_resource(
            uri="test://resource", name="Test Resource", description="A test resource"
        )

        # Try to register duplicate
        with pytest.raises(ValueError, match="already registered"):
            server.register_resource(
                uri="test://resource",
                name="Another Resource",
                description="Another resource",
            )

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test starting server when already running raises error."""
        server = PytestAnalyzerMCPServer()
        server._running = True

        with pytest.raises(RuntimeError, match="already running"):
            await server.start()

    @pytest.mark.asyncio
    async def test_start_invalid_transport(self):
        """Test starting server with invalid transport raises error."""
        server = PytestAnalyzerMCPServer(transport_type="invalid")

        with pytest.raises(RuntimeError, match="Unsupported transport type"):
            await server.start()

    @pytest.mark.asyncio
    @patch("pytest_analyzer.mcp.server.stdio_server")
    async def test_start_stdio_success(self, mock_stdio_server):
        """Test successful STDIO server start."""
        server = PytestAnalyzerMCPServer(transport_type="stdio")

        # Mock the async context manager
        mock_streams = (AsyncMock(), AsyncMock())
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_streams)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_stdio_server.return_value = mock_context

        # Mock the server run method to return immediately
        server.mcp_server.run = AsyncMock()

        await server.start()

        assert server.is_running
        mock_stdio_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_http_not_implemented(self):
        """Test HTTP server start raises NotImplementedError."""
        server = PytestAnalyzerMCPServer(transport_type="http")

        with pytest.raises(
            NotImplementedError, match="HTTP transport not yet implemented"
        ):
            await server.start()

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """Test stopping server when not running logs warning."""
        server = PytestAnalyzerMCPServer()

        with patch.object(server.logger, "warning") as mock_warning:
            await server.stop()
            mock_warning.assert_called_once_with("Server is not running")

    @pytest.mark.asyncio
    async def test_stop_success(self):
        """Test successful server stop."""
        server = PytestAnalyzerMCPServer()
        server._running = True

        # Add some tools and resources to test cleanup
        server._registered_tools["test"] = MagicMock()
        server._registered_resources["test"] = {}

        await server.stop()

        assert not server.is_running
        assert len(server.get_registered_tools()) == 0
        assert len(server.get_registered_resources()) == 0
        assert server._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_lifespan_context_manager(self):
        """Test server lifespan context manager."""
        server = PytestAnalyzerMCPServer()

        async with server.lifespan() as ctx_server:
            assert ctx_server is server

    @pytest.mark.asyncio
    async def test_lifespan_context_manager_exception(self):
        """Test server lifespan context manager with exception."""
        server = PytestAnalyzerMCPServer()

        with pytest.raises(ValueError):
            async with server.lifespan():
                raise ValueError("Test exception")

    def test_get_server_capabilities_empty(self):
        """Test server capabilities with no registered tools/resources."""
        server = PytestAnalyzerMCPServer()
        capabilities = server._get_server_capabilities()

        assert capabilities["tools"] is None
        assert capabilities["resources"] is None

    def test_get_server_capabilities_with_tools_and_resources(self):
        """Test server capabilities with registered tools and resources."""
        server = PytestAnalyzerMCPServer()

        # Add a tool and resource
        server._registered_tools["test_tool"] = MagicMock()
        server._registered_resources["test_resource"] = {}

        capabilities = server._get_server_capabilities()

        assert capabilities["tools"] == {"listChanged": True}
        assert capabilities["resources"] == {"subscribe": True, "listChanged": True}

    @pytest.mark.asyncio
    async def test_wait_for_shutdown(self):
        """Test waiting for shutdown signal."""
        server = PytestAnalyzerMCPServer()

        # Set the shutdown event after a short delay
        async def set_shutdown():
            await asyncio.sleep(0.1)
            server._shutdown_event.set()

        task = asyncio.create_task(set_shutdown())
        await server.wait_for_shutdown()
        await task

    def test_string_representations(self):
        """Test string representations of server."""
        server = PytestAnalyzerMCPServer(
            transport_type="http", host="localhost", port=8080
        )

        str_repr = str(server)
        assert "PytestAnalyzerMCPServer" in str_repr
        assert "transport=http" in str_repr
        assert "running=False" in str_repr

        repr_str = repr(server)
        assert "transport_type='http'" in repr_str
        assert "host='localhost'" in repr_str
        assert "port=8080" in repr_str
        assert "running=False" in repr_str
        assert "tools=0" in repr_str
        assert "resources=0" in repr_str


class TestMCPServerFactory:
    """Test cases for MCPServerFactory."""

    def test_create_server_default(self):
        """Test creating server with default settings."""
        server = MCPServerFactory.create_server()

        assert isinstance(server, PytestAnalyzerMCPServer)
        assert server.transport_type == "stdio"
        assert server.host == "127.0.0.1"
        assert server.port == 8000

    def test_create_server_custom(self):
        """Test creating server with custom settings."""
        settings = Settings()
        server = MCPServerFactory.create_server(
            settings=settings, transport_type="http", host="0.0.0.0", port=9000
        )

        assert server.settings is settings
        assert server.transport_type == "http"
        assert server.host == "0.0.0.0"
        assert server.port == 9000

    def test_create_stdio_server(self):
        """Test creating STDIO server."""
        settings = Settings()
        server = MCPServerFactory.create_stdio_server(settings)

        assert server.settings is settings
        assert server.transport_type == "stdio"

    def test_create_http_server(self):
        """Test creating HTTP server."""
        settings = Settings()
        server = MCPServerFactory.create_http_server(
            settings=settings, host="localhost", port=9000
        )

        assert server.settings is settings
        assert server.transport_type == "http"
        assert server.host == "localhost"
        assert server.port == 9000

    def test_create_http_server_defaults(self):
        """Test creating HTTP server with default host/port."""
        server = MCPServerFactory.create_http_server()

        assert server.transport_type == "http"
        assert server.host == "127.0.0.1"
        assert server.port == 8000


class TestMCPServerIntegration:
    """Integration test cases for MCP server."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test complete server lifecycle."""
        server = MCPServerFactory.create_stdio_server()

        # Verify initial state
        assert not server.is_running
        assert len(server.get_registered_tools()) == 0

        # Register a tool
        def test_handler():
            return {"result": "success"}

        with (
            patch.object(server.mcp_server, "list_tools") as mock_list,
            patch.object(server.mcp_server, "call_tool") as mock_call,
        ):
            mock_list.return_value = MagicMock()
            mock_call.return_value = MagicMock()

            server.register_tool("test_tool", "Test tool", test_handler)

            # Verify tool registration
            assert len(server.get_registered_tools()) == 1
            assert "test_tool" in server.get_registered_tools()

        # Register a resource
        server.register_resource(
            uri="test://example",
            name="Example Resource",
            description="An example resource",
        )

        # Verify resource registration
        assert len(server.get_registered_resources()) == 1
        assert "test://example" in server.get_registered_resources()

        # Test capabilities
        capabilities = server._get_server_capabilities()
        assert capabilities["tools"] is not None
        assert capabilities["resources"] is not None

        # Test cleanup
        await server._cleanup()
        assert len(server.get_registered_tools()) == 0
        assert len(server.get_registered_resources()) == 0

    def test_error_handling_integration(self):
        """Test error handling integration with cross-cutting concerns."""
        server = PytestAnalyzerMCPServer()

        # Test tool registration error handling
        with pytest.raises(ValueError, match="already registered"):
            with (
                patch.object(server.mcp_server, "list_tools") as mock_list,
                patch.object(server.mcp_server, "call_tool") as mock_call,
            ):
                mock_list.return_value = MagicMock()
                mock_call.return_value = MagicMock()

                server.register_tool("test", "Test", lambda: None)
                server.register_tool("test", "Test again", lambda: None)

        # Test resource registration error handling
        with pytest.raises(ValueError, match="already registered"):
            server.register_resource("test://uri", "Test", "Test")
            server.register_resource("test://uri", "Test again", "Test again")
