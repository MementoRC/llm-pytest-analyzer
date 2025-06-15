# This file defines the structure of configuration objects using Pydantic.
# It helps avoid circular dependencies by separating the type definition from its usage.

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import (
    BaseModel,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


# --- Security Settings Model ---
class SecuritySettings(BaseModel):
    """Comprehensive security settings for the MCP server."""

    # Input validation
    path_allowlist: List[str] = Field(default_factory=list)  # Allowed base paths
    allowed_file_types: List[str] = Field(
        default_factory=lambda: [".py", ".txt", ".json", ".xml"]
    )
    max_file_size_mb: Optional[float] = Field(default=10.0, gt=0)  # Max file size in MB
    enable_input_sanitization: bool = True

    # File system access
    restrict_to_project_dir: bool = True
    enable_backup: bool = True  # Require backup/rollback for write ops

    # Authentication (HTTP)
    require_authentication: bool = False
    auth_token: Optional[str] = None
    require_client_certificate: bool = False
    allowed_client_certs: List[str] = Field(default_factory=list)
    role_based_access: bool = False
    allowed_roles: Set[str] = Field(
        default_factory=lambda: {"admin", "user", "readonly"}
    )

    # Rate limiting
    max_requests_per_window: int = Field(default=100, gt=0)
    rate_limit_window_seconds: int = Field(default=60, gt=0)
    abuse_threshold: int = Field(default=200, ge=0)
    abuse_ban_count: int = Field(default=3, ge=0)
    max_resource_usage_mb: float = Field(default=100.0, gt=0)

    # Misc
    enable_resource_usage_monitoring: bool = True

    @field_validator("allowed_file_types")
    @classmethod
    def validate_file_types(cls, v: List[str]) -> List[str]:
        """Validate that file types start with a dot."""
        if v and not all(t.startswith(".") for t in v):
            raise ValueError(
                "allowed_file_types must be a list of file extensions starting with '.'"
            )
        return v


class MCPSettings(BaseModel):
    """Configuration settings for the MCP server."""

    # Transport settings
    transport_type: str = "stdio"  # Transport type: "stdio" or "http"
    http_host: str = "127.0.0.1"  # Host for HTTP transport
    http_port: int = 8000  # Port for HTTP transport

    # Security settings
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    enable_authentication: bool = Field(
        default=False, deprecated="Use security.require_authentication"
    )
    auth_token: Optional[str] = Field(
        default=None, deprecated="Use security.auth_token"
    )
    max_request_size_mb: int = Field(default=10, gt=0)  # Maximum request size in MB

    # Tool settings
    tool_timeout_seconds: int = Field(default=30, gt=0)  # Timeout for tool execution
    max_concurrent_requests: int = Field(
        default=10, gt=0
    )  # Maximum concurrent tool requests
    enable_async_execution: bool = True  # Whether to enable async tool execution

    # Resource settings
    enable_resources: bool = True  # Whether to enable MCP resources
    max_resource_size_mb: int = Field(default=50, gt=0)  # Maximum resource size in MB
    resource_cache_ttl_seconds: int = 300  # Resource cache TTL

    # Logging and monitoring
    enable_detailed_logging: bool = False  # Whether to enable detailed MCP logging
    log_requests: bool = False  # Whether to log all MCP requests/responses
    enable_metrics: bool = True  # Whether to enable metrics collection

    # Server lifecycle settings
    startup_timeout_seconds: int = Field(default=30, gt=0)  # Timeout for server startup
    shutdown_timeout_seconds: int = Field(
        default=30, gt=0
    )  # Timeout for graceful shutdown
    heartbeat_interval_seconds: int = 60  # Heartbeat interval for health checks

    @field_validator("transport_type")
    @classmethod
    def validate_transport_type(cls, v: str) -> str:
        """Validate transport type."""
        if v not in ["stdio", "http"]:
            raise ValueError(
                f"Invalid transport_type: '{v}'. Must be 'stdio' or 'http'"
            )
        return v

    @model_validator(mode="after")
    def validate_http_settings(self) -> "MCPSettings":
        """Validate HTTP-specific settings."""
        if self.transport_type == "http":
            if not (1 <= self.http_port <= 65535):
                raise ValueError(
                    f"Invalid http_port: {self.http_port}. Must be between 1 and 65535"
                )
        return self

    @model_validator(mode="before")
    @classmethod
    def handle_deprecated_auth(cls, data: Any) -> Any:
        """Sync deprecated auth fields to the new security model for backward compatibility."""
        if isinstance(data, dict):
            # Ensure security object exists if we need to modify it
            security_data = data.get("security", {})
            modified = False

            if data.get("enable_authentication"):
                security_data["require_authentication"] = True
                modified = True

            if data.get("auth_token"):
                security_data["auth_token"] = data.get("auth_token")
                modified = True

            if modified:
                data["security"] = security_data

        return data


# --- LLM Settings Model ---
class LLMSettings(BaseModel):
    """Configuration settings for LLM-based suggestions."""

    use_llm: bool = True  # Whether to use LLM-based suggestions
    llm_timeout: int = 60  # Timeout for LLM requests in seconds
    llm_api_key: Optional[str] = None  # API key for LLM service
    llm_model: str = "auto"  # Model to use (auto selects available models)
    llm_provider: str = "auto"  # Provider to use (anthropic, openai, azure, etc.)
    use_fallback: bool = True  # Whether to try fallback providers if primary fails
    auto_apply: bool = False  # Whether to automatically apply suggested fixes

    # Provider-specific settings
    anthropic_api_key: Optional[str] = None  # Anthropic API key
    openai_api_key: Optional[str] = None  # OpenAI API key
    azure_api_key: Optional[str] = None  # Azure OpenAI API key
    azure_endpoint: Optional[str] = None  # Azure OpenAI endpoint
    azure_api_version: str = "2023-05-15"  # Azure OpenAI API version
    together_api_key: Optional[str] = None  # Together.ai API key
    ollama_host: str = "localhost"  # Ollama host
    ollama_port: int = 11434  # Ollama port


# --- Main Settings Model ---
class Settings(BaseModel):
    """Configuration settings for the pytest analyzer."""

    # Pytest execution settings
    pytest_timeout: int = 300  # Maximum time in seconds for pytest execution
    pytest_args: List[str] = Field(default_factory=list)  # Additional pytest arguments

    # Resource limits
    max_memory_mb: int = 1024  # Memory limit in MB
    parser_timeout: int = 30  # Timeout for parsing operations
    analyzer_timeout: int = 60  # Timeout for analysis operations

    # Extraction settings
    max_failures: int = 100  # Maximum number of failures to process
    preferred_format: str = "json"  # Preferred output format: json, xml, or text

    # Analysis settings
    max_suggestions: int = 3  # Maximum suggestions overall
    max_suggestions_per_failure: int = 3  # Maximum suggestions per failure
    min_confidence: float = 0.5  # Minimum confidence for suggestions

    # LLM settings (top-level for backward compatibility)
    use_llm: bool = True  # Whether to use LLM-based suggestions
    llm_timeout: int = 60  # Timeout for LLM requests in seconds
    llm_api_key: Optional[str] = None  # API key for LLM service
    llm_model: str = "auto"  # Model to use (auto selects available models)
    llm_provider: str = "auto"  # Provider to use (anthropic, openai, azure, etc.)
    use_fallback: bool = True  # Whether to try fallback providers if primary fails
    auto_apply: bool = False  # Whether to automatically apply suggested fixes
    anthropic_api_key: Optional[str] = None  # Anthropic API key
    openai_api_key: Optional[str] = None  # OpenAI API key
    azure_api_key: Optional[str] = None  # Azure OpenAI API key
    azure_endpoint: Optional[str] = None  # Azure OpenAI endpoint
    azure_api_version: str = "2023-05-15"  # Azure OpenAI API version
    together_api_key: Optional[str] = None  # Together.ai API key
    ollama_host: str = "localhost"  # Ollama host
    ollama_port: int = 11434  # Ollama port

    # Git integration settings
    check_git: bool = True  # Whether to check for Git compatibility
    auto_init_git: bool = False  # Whether to auto-initialize Git without prompting
    use_git_branches: bool = True  # Whether to create branches for fix suggestions

    # Path settings
    project_root: Path = Field(
        default_factory=Path.cwd
    )  # Root directory of the project
    mock_directories: Dict[str, str] = Field(
        default_factory=dict
    )  # Absolute path mappings

    # Async processing settings
    batch_size: int = 5  # Number of failures to process in each batch in async mode
    max_concurrency: int = 10  # Maximum concurrent LLM requests in async mode

    # Logging settings
    log_level: str = "INFO"  # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    # Environment Manager settings
    environment_manager: Optional[str] = (
        None  # Override environment manager detection (pixi, poetry, hatch, uv, pipenv, pip+venv)
    )

    # MCP Server settings
    mcp: MCPSettings = Field(default_factory=MCPSettings)  # MCP server configuration

    # Backward compatibility properties
    debug: bool = False  # Enable debug mode (backward compatibility)

    @computed_field
    def llm(self) -> LLMSettings:
        """Return an LLMSettings instance from top-level settings for section-based access."""
        return LLMSettings(
            use_llm=self.use_llm,
            llm_timeout=self.llm_timeout,
            llm_api_key=self.llm_api_key,
            llm_model=self.llm_model,
            llm_provider=self.llm_provider,
            use_fallback=self.use_fallback,
            auto_apply=self.auto_apply,
            anthropic_api_key=self.anthropic_api_key,
            openai_api_key=self.openai_api_key,
            azure_api_key=self.azure_api_key,
            azure_endpoint=self.azure_endpoint,
            azure_api_version=self.azure_api_version,
            together_api_key=self.together_api_key,
            ollama_host=self.ollama_host,
            ollama_port=self.ollama_port,
        )

    @field_validator("project_root", mode="before")
    @classmethod
    def ensure_project_root_is_path(cls, v: Any) -> Path:
        """Ensure project_root is a Path object, defaulting to CWD if None."""
        if v is None:
            return Path.cwd()
        return Path(v)

    @model_validator(mode="after")
    def sync_debug_and_log_level(self) -> "Settings":
        """Synchronize debug flag and log_level for backward compatibility."""
        if self.debug and self.log_level.upper() != "DEBUG":
            self.log_level = "DEBUG"
        elif self.log_level.upper() == "DEBUG" and not self.debug:
            self.debug = True
        return self

    @field_validator("environment_manager")
    @classmethod
    def validate_environment_manager(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize the environment_manager value."""
        if v is not None:
            normalized_manager = v.lower()
            VALID_MANAGERS = {
                "pixi",
                "poetry",
                "hatch",
                "uv",
                "pipenv",
                "pip+venv",
            }
            if normalized_manager not in VALID_MANAGERS:
                raise ValueError(
                    f"Invalid environment_manager: '{v}'. "
                    f"Must be one of {VALID_MANAGERS} (case-insensitive), or None."
                )
            return normalized_manager
        return None
