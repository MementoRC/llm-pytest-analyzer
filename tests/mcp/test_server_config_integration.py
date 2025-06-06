"""Tests for MCP server configuration integration."""

import re

from pytest_analyzer.mcp.server import MCPServerFactory, PytestAnalyzerMCPServer
from pytest_analyzer.utils.config_types import MCPSettings, Settings


class TestMCPServerConfigIntegration:
    """Test MCP server integration with new configuration system."""

    def test_server_uses_mcp_settings_defaults(self):
        """Test that MCP server uses default MCP settings."""
        server = PytestAnalyzerMCPServer()

        # Should use default MCP settings
        assert server.mcp_settings.transport_type == "stdio"
        assert server.mcp_settings.http_host == "127.0.0.1"
        assert server.mcp_settings.http_port == 8000
        assert server.mcp_settings.tool_timeout_seconds == 30

    def test_server_uses_custom_mcp_settings(self):
        """Test that MCP server uses custom MCP settings."""
        custom_mcp = MCPSettings(
            transport_type="http",
            http_host="0.0.0.0",
            http_port=9000,
            tool_timeout_seconds=60,
            enable_authentication=True,
        )

        settings = Settings(mcp=custom_mcp)
        server = PytestAnalyzerMCPServer(settings=settings)

        # Should use custom MCP settings
        assert server.mcp_settings.transport_type == "http"
        assert server.mcp_settings.http_host == "0.0.0.0"
        assert server.mcp_settings.http_port == 9000
        assert server.mcp_settings.tool_timeout_seconds == 60
        assert server.mcp_settings.enable_authentication is True

    def test_server_factory_stdio_override(self):
        """Test that STDIO factory method overrides transport type."""
        # Start with HTTP settings
        custom_mcp = MCPSettings(transport_type="http", http_port=9000)
        settings = Settings(mcp=custom_mcp)

        # Use STDIO factory - should override transport to stdio
        server = MCPServerFactory.create_stdio_server(settings)

        assert server.mcp_settings.transport_type == "stdio"
        # Other settings should be preserved
        assert server.mcp_settings.http_port == 9000

    def test_server_factory_http_override(self):
        """Test that HTTP factory method overrides settings."""
        # Start with STDIO settings
        custom_mcp = MCPSettings(transport_type="stdio")
        settings = Settings(mcp=custom_mcp)

        # Use HTTP factory with specific host/port - should override
        server = MCPServerFactory.create_http_server(
            settings=settings, host="192.168.1.100", port=8080
        )

        assert server.mcp_settings.transport_type == "http"
        assert server.mcp_settings.http_host == "192.168.1.100"
        assert server.mcp_settings.http_port == 8080

    def test_server_factory_http_no_override(self):
        """Test that HTTP factory uses settings when no override provided."""
        custom_mcp = MCPSettings(
            transport_type="stdio",  # Will be overridden to http
            http_host="custom.host.com",
            http_port=7000,
        )
        settings = Settings(mcp=custom_mcp)

        # Use HTTP factory without host/port override
        server = MCPServerFactory.create_http_server(settings=settings)

        assert server.mcp_settings.transport_type == "http"
        assert server.mcp_settings.http_host == "custom.host.com"
        assert server.mcp_settings.http_port == 7000

    def test_server_logging_includes_config_info(self, caplog):
        """Test that server logs include configuration information."""
        custom_mcp = MCPSettings(
            transport_type="http", http_host="test.example.com", http_port=8888
        )
        settings = Settings(mcp=custom_mcp)

        PytestAnalyzerMCPServer(settings=settings)

        # Check that initialization log includes config info
        log_records = [
            record
            for record in caplog.records
            if record.name == "PytestAnalyzerMCPServer"
        ]

        assert len(log_records) > 0

        # Should mention transport type, host, and port
        init_message = log_records[0].message
        assert "http transport" in init_message
        assert re.search(r'\btest\.example\.com\b', init_message)
        assert "8888" in init_message
