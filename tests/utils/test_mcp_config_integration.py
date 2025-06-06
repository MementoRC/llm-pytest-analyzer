"""Tests for MCP configuration integration."""

import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from pytest_analyzer.utils.config_types import MCPSettings, Settings
from pytest_analyzer.utils.configuration import ConfigurationManager


class TestMCPSettings:
    """Test MCPSettings dataclass validation and defaults."""

    def test_mcp_settings_defaults(self):
        """Test MCPSettings default values."""
        mcp = MCPSettings()
        
        # Transport settings
        assert mcp.transport_type == "stdio"
        assert mcp.http_host == "127.0.0.1"
        assert mcp.http_port == 8000
        
        # Security settings
        assert mcp.enable_authentication is False
        assert mcp.auth_token is None
        assert mcp.max_request_size_mb == 10
        
        # Tool settings
        assert mcp.tool_timeout_seconds == 30
        assert mcp.max_concurrent_requests == 10
        assert mcp.enable_async_execution is True
        
        # Resource settings
        assert mcp.enable_resources is True
        assert mcp.max_resource_size_mb == 50
        assert mcp.resource_cache_ttl_seconds == 300

    def test_mcp_settings_validation(self):
        """Test MCPSettings validation in __post_init__."""
        # Test valid transport types
        mcp_stdio = MCPSettings(transport_type="stdio")
        assert mcp_stdio.transport_type == "stdio"
        
        mcp_http = MCPSettings(transport_type="http")
        assert mcp_http.transport_type == "http"
        
        # Test invalid transport type
        with pytest.raises(ValueError, match="Invalid transport_type"):
            MCPSettings(transport_type="invalid")

    def test_mcp_settings_timeout_validation(self):
        """Test timeout validation."""
        with pytest.raises(ValueError, match="tool_timeout_seconds must be positive"):
            MCPSettings(tool_timeout_seconds=0)
        
        with pytest.raises(ValueError, match="startup_timeout_seconds must be positive"):
            MCPSettings(startup_timeout_seconds=-1)
        
        with pytest.raises(ValueError, match="shutdown_timeout_seconds must be positive"):
            MCPSettings(shutdown_timeout_seconds=0)

    def test_mcp_settings_port_validation(self):
        """Test HTTP port validation."""
        # Valid ports
        mcp = MCPSettings(transport_type="http", http_port=8080)
        assert mcp.http_port == 8080
        
        # Invalid ports for HTTP transport
        with pytest.raises(ValueError, match="Invalid http_port"):
            MCPSettings(transport_type="http", http_port=0)
        
        with pytest.raises(ValueError, match="Invalid http_port"):
            MCPSettings(transport_type="http", http_port=70000)

    def test_mcp_settings_size_validation(self):
        """Test size limit validation."""
        with pytest.raises(ValueError, match="max_request_size_mb must be positive"):
            MCPSettings(max_request_size_mb=0)
        
        with pytest.raises(ValueError, match="max_resource_size_mb must be positive"):
            MCPSettings(max_resource_size_mb=-1)

    def test_mcp_settings_concurrency_validation(self):
        """Test concurrency validation."""
        with pytest.raises(ValueError, match="max_concurrent_requests must be positive"):
            MCPSettings(max_concurrent_requests=0)


class TestSettingsMCPIntegration:
    """Test MCP integration with the main Settings class."""

    def test_settings_default_mcp(self):
        """Test that Settings includes default MCPSettings."""
        settings = Settings()
        
        # Check that mcp is an MCPSettings instance
        assert isinstance(settings.mcp, MCPSettings)
        assert settings.mcp.transport_type == "stdio"
        assert settings.mcp.http_port == 8000

    def test_settings_custom_mcp(self):
        """Test Settings with custom MCPSettings."""
        custom_mcp = MCPSettings(
            transport_type="http",
            http_port=9000,
            enable_authentication=True
        )
        
        settings = Settings(mcp=custom_mcp)
        
        assert settings.mcp.transport_type == "http"
        assert settings.mcp.http_port == 9000
        assert settings.mcp.enable_authentication is True


class TestConfigurationManagerMCPIntegration:
    """Test ConfigurationManager integration with MCP settings."""

    def setup_method(self):
        """Set up test environment."""
        self.config_manager = ConfigurationManager()

    def test_load_mcp_from_env_variables(self):
        """Test loading MCP settings from environment variables."""
        env_vars = {
            "PYTEST_ANALYZER_MCP_TRANSPORT_TYPE": "http",
            "PYTEST_ANALYZER_MCP_HTTP_PORT": "9000",
            "PYTEST_ANALYZER_MCP_ENABLE_AUTHENTICATION": "true",
            "PYTEST_ANALYZER_MCP_TOOL_TIMEOUT_SECONDS": "45",
            "PYTEST_ANALYZER_MCP_MAX_REQUEST_SIZE_MB": "20"
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            self.config_manager.load_config(force_reload=True)
            settings = self.config_manager.get_settings()
            
            assert settings.mcp.transport_type == "http"
            assert settings.mcp.http_port == 9000
            assert settings.mcp.enable_authentication is True
            assert settings.mcp.tool_timeout_seconds == 45
            assert settings.mcp.max_request_size_mb == 20

    def test_load_mcp_from_yaml_file(self):
        """Test loading MCP settings from YAML configuration file."""
        config_data = {
            "mcp": {
                "transport_type": "http",
                "http_host": "0.0.0.0",
                "http_port": 8080,
                "enable_authentication": True,
                "tool_timeout_seconds": 60,
                "enable_detailed_logging": True
            },
            "use_llm": False,
            "max_failures": 50
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file_path = f.name
        
        try:
            config_manager = ConfigurationManager(config_file_path=config_file_path)
            config_manager.load_config()
            settings = config_manager.get_settings()
            
            # Check MCP settings
            assert settings.mcp.transport_type == "http"
            assert settings.mcp.http_host == "0.0.0.0"
            assert settings.mcp.http_port == 8080
            assert settings.mcp.enable_authentication is True
            assert settings.mcp.tool_timeout_seconds == 60
            assert settings.mcp.enable_detailed_logging is True
            
            # Check other settings
            assert settings.use_llm is False
            assert settings.max_failures == 50
            
        finally:
            os.unlink(config_file_path)

    def test_env_variables_override_yaml(self):
        """Test that environment variables override YAML configuration for MCP settings."""
        # Create YAML config
        config_data = {
            "mcp": {
                "transport_type": "stdio",
                "http_port": 8000,
                "enable_authentication": False
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file_path = f.name
        
        # Set environment variables that should override YAML
        env_vars = {
            "PYTEST_ANALYZER_MCP_TRANSPORT_TYPE": "http",
            "PYTEST_ANALYZER_MCP_HTTP_PORT": "9000",
            "PYTEST_ANALYZER_MCP_ENABLE_AUTHENTICATION": "true"
        }
        
        try:
            with patch.dict(os.environ, env_vars, clear=False):
                config_manager = ConfigurationManager(config_file_path=config_file_path)
                config_manager.load_config()
                settings = config_manager.get_settings()
                
                # Environment variables should override YAML
                assert settings.mcp.transport_type == "http"  # From env, not stdio from YAML
                assert settings.mcp.http_port == 9000  # From env, not 8000 from YAML
                assert settings.mcp.enable_authentication is True  # From env, not False from YAML
                
        finally:
            os.unlink(config_file_path)

    def test_invalid_mcp_env_variable_handling(self):
        """Test handling of invalid MCP environment variables."""
        env_vars = {
            "PYTEST_ANALYZER_MCP_TRANSPORT_TYPE": "invalid_transport",
            "PYTEST_ANALYZER_MCP_HTTP_PORT": "not_a_number",
            "PYTEST_ANALYZER_MCP_TOOL_TIMEOUT_SECONDS": "-1"
        }
        
        with patch.dict(os.environ, env_vars, clear=False):
            # Should not raise an exception, but should use defaults
            self.config_manager.load_config(force_reload=True)
            settings = self.config_manager.get_settings()
            
            # Should fall back to defaults due to validation errors
            assert isinstance(settings.mcp, MCPSettings)
            # The invalid values should not be applied due to validation

    def test_partial_mcp_configuration(self):
        """Test partial MCP configuration with mixed sources."""
        # YAML with some MCP settings
        config_data = {
            "mcp": {
                "transport_type": "http",
                "http_port": 8080
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file_path = f.name
        
        # Environment variable for additional MCP setting
        env_vars = {
            "PYTEST_ANALYZER_MCP_ENABLE_AUTHENTICATION": "true"
        }
        
        try:
            with patch.dict(os.environ, env_vars, clear=False):
                config_manager = ConfigurationManager(config_file_path=config_file_path)
                config_manager.load_config()
                settings = config_manager.get_settings()
                
                # Should combine YAML and env settings
                assert settings.mcp.transport_type == "http"  # From YAML
                assert settings.mcp.http_port == 8080  # From YAML
                assert settings.mcp.enable_authentication is True  # From env
                
                # Defaults should be preserved for unspecified settings
                assert settings.mcp.tool_timeout_seconds == 30  # Default
                
        finally:
            os.unlink(config_file_path)

    def test_mcp_settings_yaml_validation_error(self):
        """Test handling of invalid MCP settings in YAML."""
        config_data = {
            "mcp": {
                "transport_type": "invalid",
                "http_port": -1
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file_path = f.name
        
        try:
            config_manager = ConfigurationManager(config_file_path=config_file_path)
            config_manager.load_config()
            settings = config_manager.get_settings()
            
            # Should fall back to default MCPSettings due to validation error
            assert isinstance(settings.mcp, MCPSettings)
            assert settings.mcp.transport_type == "stdio"  # Default
            assert settings.mcp.http_port == 8000  # Default
            
        finally:
            os.unlink(config_file_path)

    def test_empty_mcp_configuration(self):
        """Test behavior with empty MCP configuration."""
        config_data = {
            "mcp": {}
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file_path = f.name
        
        try:
            config_manager = ConfigurationManager(config_file_path=config_file_path)
            config_manager.load_config()
            settings = config_manager.get_settings()
            
            # Should use all defaults
            assert isinstance(settings.mcp, MCPSettings)
            assert settings.mcp.transport_type == "stdio"
            assert settings.mcp.http_port == 8000
            
        finally:
            os.unlink(config_file_path)