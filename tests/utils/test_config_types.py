"""
Tests for the Pydantic-based configuration models in config_types.py.

This module tests the Settings, MCPSettings, and SecuritySettings Pydantic models,
including field validation, model validation, and backward compatibility.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from pytest_analyzer.utils.config_types import MCPSettings, SecuritySettings, Settings


class TestSecuritySettings:
    """Tests for SecuritySettings Pydantic model."""

    def test_default_creation(self):
        """Test creating SecuritySettings with defaults."""
        settings = SecuritySettings()

        assert settings.path_allowlist == []
        assert settings.allowed_file_types == [".py", ".txt", ".json", ".xml"]
        assert settings.max_file_size_mb == 10.0
        assert settings.enable_input_sanitization is True
        assert settings.restrict_to_project_dir is True
        assert settings.enable_backup is True
        assert settings.require_authentication is False
        assert settings.auth_token is None
        assert settings.require_client_certificate is False
        assert settings.allowed_client_certs == []
        assert settings.role_based_access is False
        assert settings.allowed_roles == {"admin", "user", "readonly"}
        assert settings.max_requests_per_window == 100
        assert settings.rate_limit_window_seconds == 60
        assert settings.abuse_threshold == 200
        assert settings.abuse_ban_count == 3
        assert settings.max_resource_usage_mb == 100.0
        assert settings.enable_resource_usage_monitoring is True

    def test_custom_values(self):
        """Test creating SecuritySettings with custom values."""
        settings = SecuritySettings(
            path_allowlist=["/allowed/path1", "/allowed/path2"],
            allowed_file_types=[".py", ".json"],
            max_file_size_mb=50.0,
            enable_input_sanitization=False,
            restrict_to_project_dir=False,
            enable_backup=False,
            require_authentication=True,
            auth_token="test-token",
            require_client_certificate=True,
            allowed_client_certs=["cert1", "cert2"],
            role_based_access=True,
            allowed_roles={"admin", "power_user"},
            max_requests_per_window=200,
            rate_limit_window_seconds=120,
            abuse_threshold=500,
            abuse_ban_count=5,
            max_resource_usage_mb=200.0,
            enable_resource_usage_monitoring=False,
        )

        assert settings.path_allowlist == ["/allowed/path1", "/allowed/path2"]
        assert settings.allowed_file_types == [".py", ".json"]
        assert settings.max_file_size_mb == 50.0
        assert settings.enable_input_sanitization is False
        assert settings.restrict_to_project_dir is False
        assert settings.enable_backup is False
        assert settings.require_authentication is True
        assert settings.auth_token == "test-token"
        assert settings.require_client_certificate is True
        assert settings.allowed_client_certs == ["cert1", "cert2"]
        assert settings.role_based_access is True
        assert settings.allowed_roles == {"admin", "power_user"}
        assert settings.max_requests_per_window == 200
        assert settings.rate_limit_window_seconds == 120
        assert settings.abuse_threshold == 500
        assert settings.abuse_ban_count == 5
        assert settings.max_resource_usage_mb == 200.0
        assert settings.enable_resource_usage_monitoring is False

    def test_validation_positive_values(self):
        """Test validation of positive value constraints."""
        # Test valid positive values
        settings = SecuritySettings(
            max_file_size_mb=1.0,
            max_requests_per_window=1,
            rate_limit_window_seconds=1,
            max_resource_usage_mb=1.0,
        )
        assert settings.max_file_size_mb == 1.0
        assert settings.max_requests_per_window == 1
        assert settings.rate_limit_window_seconds == 1
        assert settings.max_resource_usage_mb == 1.0

    def test_validation_negative_values(self):
        """Test validation rejects negative values."""
        # Test max_file_size_mb validation
        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(max_file_size_mb=-1.0)
        assert "Input should be greater than 0" in str(exc_info.value)

        # Test max_requests_per_window validation
        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(max_requests_per_window=-1)
        assert "Input should be greater than 0" in str(exc_info.value)

        # Test rate_limit_window_seconds validation
        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(rate_limit_window_seconds=-1)
        assert "Input should be greater than 0" in str(exc_info.value)

        # Test max_resource_usage_mb validation
        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(max_resource_usage_mb=-1.0)
        assert "Input should be greater than 0" in str(exc_info.value)

    def test_validation_zero_values(self):
        """Test validation rejects zero values for positive fields."""
        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(max_file_size_mb=0.0)
        assert "Input should be greater than 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(max_requests_per_window=0)
        assert "Input should be greater than 0" in str(exc_info.value)

    def test_validation_non_negative_values(self):
        """Test validation allows zero for non-negative fields."""
        settings = SecuritySettings(abuse_threshold=0, abuse_ban_count=0)
        assert settings.abuse_threshold == 0
        assert settings.abuse_ban_count == 0

    def test_file_types_validation_valid(self):
        """Test file types validation with valid extensions."""
        settings = SecuritySettings(allowed_file_types=[".py", ".txt", ".json"])
        assert settings.allowed_file_types == [".py", ".txt", ".json"]

    def test_file_types_validation_invalid(self):
        """Test file types validation rejects invalid extensions."""
        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(allowed_file_types=["py", ".txt"])  # Missing dot
        assert (
            "allowed_file_types must be a list of file extensions starting with '.'"
            in str(exc_info.value)
        )

        with pytest.raises(ValidationError) as exc_info:
            SecuritySettings(allowed_file_types=[".py", "txt"])  # Missing dot
        assert (
            "allowed_file_types must be a list of file extensions starting with '.'"
            in str(exc_info.value)
        )

    def test_model_dump(self):
        """Test model serialization."""
        settings = SecuritySettings(
            max_file_size_mb=25.0, require_authentication=True, auth_token="test-token"
        )
        data = settings.model_dump()

        assert isinstance(data, dict)
        assert data["max_file_size_mb"] == 25.0
        assert data["require_authentication"] is True
        assert data["auth_token"] == "test-token"
        assert "allowed_file_types" in data


class TestMCPSettings:
    """Tests for MCPSettings Pydantic model."""

    def test_default_creation(self):
        """Test creating MCPSettings with defaults."""
        settings = MCPSettings()

        assert settings.transport_type == "stdio"
        assert settings.http_host == "127.0.0.1"
        assert settings.http_port == 8000
        assert isinstance(settings.security, SecuritySettings)
        assert settings.enable_authentication is False
        assert settings.auth_token is None
        assert settings.max_request_size_mb == 10
        assert settings.tool_timeout_seconds == 30
        assert settings.max_concurrent_requests == 10
        assert settings.enable_async_execution is True
        assert settings.enable_resources is True
        assert settings.max_resource_size_mb == 50
        assert settings.resource_cache_ttl_seconds == 300
        assert settings.enable_detailed_logging is False
        assert settings.log_requests is False
        assert settings.enable_metrics is True
        assert settings.startup_timeout_seconds == 30
        assert settings.shutdown_timeout_seconds == 30
        assert settings.heartbeat_interval_seconds == 60

    def test_transport_type_validation_valid(self):
        """Test valid transport type values."""
        stdio_settings = MCPSettings(transport_type="stdio")
        assert stdio_settings.transport_type == "stdio"

        http_settings = MCPSettings(transport_type="http")
        assert http_settings.transport_type == "http"

    def test_transport_type_validation_invalid(self):
        """Test invalid transport type values."""
        with pytest.raises(ValidationError) as exc_info:
            MCPSettings(transport_type="invalid")
        assert "Invalid transport_type: 'invalid'. Must be 'stdio' or 'http'" in str(
            exc_info.value
        )

    def test_http_port_validation_valid(self):
        """Test valid HTTP port values."""
        settings = MCPSettings(transport_type="http", http_port=8080)
        assert settings.http_port == 8080

        # Test edge cases
        settings_min = MCPSettings(transport_type="http", http_port=1)
        assert settings_min.http_port == 1

        settings_max = MCPSettings(transport_type="http", http_port=65535)
        assert settings_max.http_port == 65535

    def test_http_port_validation_invalid(self):
        """Test invalid HTTP port values."""
        with pytest.raises(ValidationError) as exc_info:
            MCPSettings(transport_type="http", http_port=0)
        assert "Invalid http_port: 0. Must be between 1 and 65535" in str(
            exc_info.value
        )

        with pytest.raises(ValidationError) as exc_info:
            MCPSettings(transport_type="http", http_port=65536)
        assert "Invalid http_port: 65536. Must be between 1 and 65535" in str(
            exc_info.value
        )

    def test_positive_value_constraints(self):
        """Test positive value constraints."""
        # Test valid positive values
        settings = MCPSettings(
            max_request_size_mb=1,
            tool_timeout_seconds=1,
            max_concurrent_requests=1,
            max_resource_size_mb=1,
            startup_timeout_seconds=1,
            shutdown_timeout_seconds=1,
        )
        assert settings.max_request_size_mb == 1
        assert settings.tool_timeout_seconds == 1
        assert settings.max_concurrent_requests == 1
        assert settings.max_resource_size_mb == 1
        assert settings.startup_timeout_seconds == 1
        assert settings.shutdown_timeout_seconds == 1

    def test_positive_value_constraints_invalid(self):
        """Test validation rejects non-positive values."""
        with pytest.raises(ValidationError) as exc_info:
            MCPSettings(max_request_size_mb=0)
        assert "Input should be greater than 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            MCPSettings(tool_timeout_seconds=0)
        assert "Input should be greater than 0" in str(exc_info.value)

    def test_deprecated_auth_backward_compatibility(self):
        """Test backward compatibility with deprecated auth fields."""
        # Test enable_authentication sync
        settings = MCPSettings(enable_authentication=True)
        assert settings.security.require_authentication is True

        # Test auth_token sync
        settings = MCPSettings(auth_token="test-token")
        assert settings.security.auth_token == "test-token"

        # Test both together
        settings = MCPSettings(enable_authentication=True, auth_token="test-token")
        assert settings.security.require_authentication is True
        assert settings.security.auth_token == "test-token"

    def test_nested_security_settings(self):
        """Test nested SecuritySettings configuration."""
        security_config = {
            "require_authentication": True,
            "auth_token": "nested-token",
            "max_requests_per_window": 200,
        }
        settings = MCPSettings(security=security_config)

        assert settings.security.require_authentication is True
        assert settings.security.auth_token == "nested-token"
        assert settings.security.max_requests_per_window == 200

    def test_model_dump_with_nested(self):
        """Test model serialization with nested models."""
        settings = MCPSettings(
            transport_type="http",
            http_port=8080,
            security={"require_authentication": True, "auth_token": "test"},
        )
        data = settings.model_dump()

        assert isinstance(data, dict)
        assert data["transport_type"] == "http"
        assert data["http_port"] == 8080
        assert isinstance(data["security"], dict)
        assert data["security"]["require_authentication"] is True
        assert data["security"]["auth_token"] == "test"


class TestSettings:
    """Tests for main Settings Pydantic model."""

    def test_default_creation(self):
        """Test creating Settings with defaults."""
        settings = Settings()

        # Test core pytest settings
        assert settings.pytest_timeout == 300
        assert settings.pytest_args == []

        # Test resource limits
        assert settings.max_memory_mb == 1024
        assert settings.parser_timeout == 30
        assert settings.analyzer_timeout == 60

        # Test extraction settings
        assert settings.max_failures == 100
        assert settings.preferred_format == "json"

        # Test analysis settings
        assert settings.max_suggestions == 3
        assert settings.max_suggestions_per_failure == 3
        assert settings.min_confidence == 0.5

        # Test LLM settings
        assert settings.use_llm is True
        assert settings.llm_timeout == 60
        assert settings.llm_api_key is None
        assert settings.llm_model == "auto"
        assert settings.llm_provider == "auto"
        assert settings.use_fallback is True
        assert settings.auto_apply is False

        # Test provider-specific settings
        assert settings.anthropic_api_key is None
        assert settings.openai_api_key is None
        assert settings.azure_api_key is None
        assert settings.azure_endpoint is None
        assert settings.azure_api_version == "2023-05-15"
        assert settings.together_api_key is None
        assert settings.ollama_host == "localhost"
        assert settings.ollama_port == 11434

        # Test Git integration
        assert settings.check_git is True
        assert settings.auto_init_git is False
        assert settings.use_git_branches is True

        # Test path settings
        assert isinstance(settings.project_root, Path)
        assert settings.mock_directories == {}

        # Test async processing
        assert settings.batch_size == 5
        assert settings.max_concurrency == 10

        # Test logging
        assert settings.log_level == "INFO"

        # Test environment manager
        assert settings.environment_manager is None

        # Test MCP settings
        assert isinstance(settings.mcp, MCPSettings)

        # Test backward compatibility
        assert settings.debug is False

    def test_project_root_path_conversion(self):
        """Test project_root conversion to Path object."""
        # Test string conversion
        settings = Settings(project_root="/test/path")
        assert isinstance(settings.project_root, Path)
        assert str(settings.project_root) == "/test/path"

        # Test Path object passed directly
        test_path = Path("/direct/path")
        settings = Settings(project_root=test_path)
        assert settings.project_root == test_path

        # Test None defaults to current working directory
        settings = Settings(project_root=None)
        assert isinstance(settings.project_root, Path)
        assert settings.project_root == Path.cwd()

    def test_debug_log_level_sync(self):
        """Test synchronization between debug flag and log_level."""
        # Test debug=True sets log_level to DEBUG
        settings = Settings(debug=True)
        assert settings.debug is True
        assert settings.log_level == "DEBUG"

        # Test log_level=DEBUG sets debug=True
        settings = Settings(log_level="DEBUG")
        assert settings.debug is True
        assert settings.log_level.upper() == "DEBUG"

        # Test case insensitive log level
        settings = Settings(log_level="debug")
        assert settings.debug is True
        assert settings.log_level == "debug"  # Original case preserved

    def test_environment_manager_validation_valid(self):
        """Test valid environment manager values."""
        valid_managers = ["pixi", "poetry", "hatch", "uv", "pipenv", "pip+venv"]

        for manager in valid_managers:
            settings = Settings(environment_manager=manager)
            assert settings.environment_manager == manager.lower()

            # Test case insensitive
            settings = Settings(environment_manager=manager.upper())
            assert settings.environment_manager == manager.lower()

    def test_environment_manager_validation_invalid(self):
        """Test invalid environment manager values."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment_manager="invalid")
        assert "Invalid environment_manager: 'invalid'" in str(exc_info.value)
        assert "Must be one of" in str(exc_info.value)

    def test_environment_manager_none_allowed(self):
        """Test that None is allowed for environment_manager."""
        settings = Settings(environment_manager=None)
        assert settings.environment_manager is None

    def test_nested_mcp_settings(self):
        """Test nested MCP settings configuration."""
        mcp_config = {
            "transport_type": "http",
            "http_port": 9000,
            "security": {
                "require_authentication": True,
                "auth_token": "nested-test-token",
            },
        }
        settings = Settings(mcp=mcp_config)

        assert settings.mcp.transport_type == "http"
        assert settings.mcp.http_port == 9000
        assert settings.mcp.security.require_authentication is True
        assert settings.mcp.security.auth_token == "nested-test-token"

    def test_model_dump_complete(self):
        """Test complete model serialization."""
        settings = Settings(
            pytest_timeout=600,
            llm_model="gpt-4",
            project_root="/test/project",
            debug=True,
            mcp={"transport_type": "http", "http_port": 9000},
        )
        data = settings.model_dump()

        assert isinstance(data, dict)
        assert data["pytest_timeout"] == 600
        assert data["llm_model"] == "gpt-4"
        assert data["debug"] is True
        assert data["log_level"] == "DEBUG"  # Should be synced
        # Path objects are serialized based on pydantic's serialization mode
        assert str(data["project_root"]) == "/test/project"
        assert isinstance(data["mcp"], dict)
        assert data["mcp"]["transport_type"] == "http"

    def test_model_validation_error_handling(self):
        """Test that invalid data raises ValidationError."""
        with pytest.raises(ValidationError):
            Settings(pytest_timeout="invalid")  # Should be int

        with pytest.raises(ValidationError):
            Settings(min_confidence="invalid")  # Should be float

    def test_schema_generation(self):
        """Test JSON schema generation."""
        schema = Settings.model_json_schema()

        assert isinstance(schema, dict)
        assert "type" in schema
        assert schema["type"] == "object"
        assert "properties" in schema

        # Check some key properties exist
        properties = schema["properties"]
        assert "pytest_timeout" in properties
        assert "llm_model" in properties
        assert "project_root" in properties
        assert "mcp" in properties

        # Check nested schema - MCP schema can be referenced or inline
        mcp_schema = properties["mcp"]
        # Handle both direct properties and $ref cases
        if "properties" in mcp_schema:
            mcp_properties = mcp_schema["properties"]
            assert "transport_type" in mcp_properties
            assert "security" in mcp_properties
        elif "$ref" in mcp_schema and "$defs" in schema:
            # Schema uses references - check that MCPSettings is defined
            assert any(
                "MCPSettings" in str(key) or "MCP" in str(key)
                for key in schema["$defs"].keys()
            )


class TestModelInteraction:
    """Tests for interaction between different models."""

    def test_full_nested_configuration(self):
        """Test complete nested configuration setup."""
        config = {
            "pytest_timeout": 600,
            "llm_model": "gpt-4",
            "debug": True,
            "mcp": {
                "transport_type": "http",
                "http_port": 9000,
                "enable_authentication": True,  # Deprecated field
                "auth_token": "legacy-token",  # Deprecated field
                "security": {
                    "require_authentication": False,  # Should be overridden
                    "max_requests_per_window": 500,
                    "allowed_file_types": [".py", ".json"],
                },
            },
        }

        settings = Settings(**config)

        # Test top-level settings
        assert settings.pytest_timeout == 600
        assert settings.llm_model == "gpt-4"
        assert settings.debug is True
        assert settings.log_level == "DEBUG"

        # Test MCP settings
        assert settings.mcp.transport_type == "http"
        assert settings.mcp.http_port == 9000

        # Test backward compatibility - deprecated fields should override security
        assert (
            settings.mcp.security.require_authentication is True
        )  # From enable_authentication
        assert settings.mcp.security.auth_token == "legacy-token"  # From auth_token
        assert (
            settings.mcp.security.max_requests_per_window == 500
        )  # From nested security
        assert settings.mcp.security.allowed_file_types == [".py", ".json"]

    def test_serialization_roundtrip(self):
        """Test that models can be serialized and deserialized."""
        original = Settings(
            pytest_timeout=600,
            debug=True,
            mcp={
                "transport_type": "http",
                "security": {
                    "require_authentication": True,
                    "allowed_file_types": [".py", ".txt"],
                },
            },
        )

        # Serialize
        data = original.model_dump()

        # Deserialize
        restored = Settings(**data)

        # Compare key values
        assert restored.pytest_timeout == original.pytest_timeout
        assert restored.debug == original.debug
        assert restored.log_level == original.log_level
        assert restored.mcp.transport_type == original.mcp.transport_type
        assert (
            restored.mcp.security.require_authentication
            == original.mcp.security.require_authentication
        )
        assert (
            restored.mcp.security.allowed_file_types
            == original.mcp.security.allowed_file_types
        )
