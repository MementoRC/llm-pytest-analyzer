# This file defines the structure of configuration objects, like the Settings dataclass.
# It helps avoid circular dependencies by separating the type definition from its usage.

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class MCPSettings:
    """Configuration settings for the MCP server."""

    # Transport settings
    transport_type: str = "stdio"  # Transport type: "stdio" or "http"
    http_host: str = "127.0.0.1"  # Host for HTTP transport
    http_port: int = 8000  # Port for HTTP transport

    # Security settings
    enable_authentication: bool = False  # Whether to enable authentication
    auth_token: Optional[str] = None  # Authentication token
    max_request_size_mb: int = 10  # Maximum request size in MB

    # Tool settings
    tool_timeout_seconds: int = 30  # Timeout for tool execution
    max_concurrent_requests: int = 10  # Maximum concurrent tool requests
    enable_async_execution: bool = True  # Whether to enable async tool execution

    # Resource settings
    enable_resources: bool = True  # Whether to enable MCP resources
    max_resource_size_mb: int = 50  # Maximum resource size in MB
    resource_cache_ttl_seconds: int = 300  # Resource cache TTL

    # Logging and monitoring
    enable_detailed_logging: bool = False  # Whether to enable detailed MCP logging
    log_requests: bool = False  # Whether to log all MCP requests/responses
    enable_metrics: bool = True  # Whether to enable metrics collection

    # Server lifecycle settings
    startup_timeout_seconds: int = 30  # Timeout for server startup
    shutdown_timeout_seconds: int = 30  # Timeout for graceful shutdown
    heartbeat_interval_seconds: int = 60  # Heartbeat interval for health checks

    def __post_init__(self):
        """Validate MCP settings after initialization."""
        # Validate transport type
        if self.transport_type not in ["stdio", "http"]:
            raise ValueError(
                f"Invalid transport_type: '{self.transport_type}'. Must be 'stdio' or 'http'"
            )

        # Validate timeouts are positive
        if self.tool_timeout_seconds <= 0:
            raise ValueError("tool_timeout_seconds must be positive")
        if self.startup_timeout_seconds <= 0:
            raise ValueError("startup_timeout_seconds must be positive")
        if self.shutdown_timeout_seconds <= 0:
            raise ValueError("shutdown_timeout_seconds must be positive")

        # Validate port range for HTTP transport
        if self.transport_type == "http":
            if not (1 <= self.http_port <= 65535):
                raise ValueError(
                    f"Invalid http_port: {self.http_port}. Must be between 1 and 65535"
                )

        # Validate size limits
        if self.max_request_size_mb <= 0:
            raise ValueError("max_request_size_mb must be positive")
        if self.max_resource_size_mb <= 0:
            raise ValueError("max_resource_size_mb must be positive")

        # Validate concurrency limits
        if self.max_concurrent_requests <= 0:
            raise ValueError("max_concurrent_requests must be positive")


# --- Settings Dataclass Definition ---
# Moved here from settings.py
@dataclass
class Settings:
    """Configuration settings for the pytest analyzer."""

    # Pytest execution settings
    pytest_timeout: int = 300  # Maximum time in seconds for pytest execution
    pytest_args: List[str] = field(default_factory=list)  # Additional pytest arguments

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

    # LLM settings
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

    # Git integration settings
    check_git: bool = True  # Whether to check for Git compatibility
    auto_init_git: bool = False  # Whether to auto-initialize Git without prompting
    use_git_branches: bool = True  # Whether to create branches for fix suggestions

    # Path settings
    project_root: Optional[Path] = None  # Root directory of the project
    mock_directories: Dict[str, str] = field(
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
    mcp: MCPSettings = field(default_factory=MCPSettings)  # MCP server configuration

    # Backward compatibility properties
    debug: bool = False  # Enable debug mode (backward compatibility)

    def __post_init__(self):
        # Convert project_root to Path if it's a string
        if self.project_root and isinstance(self.project_root, str):
            self.project_root = Path(self.project_root)

        # Set default project root if not provided
        if not self.project_root:
            self.project_root = Path.cwd()

        # Synchronize debug and log_level for backward compatibility
        if self.debug and self.log_level != "DEBUG":
            self.log_level = "DEBUG"
        elif self.log_level == "DEBUG" and not self.debug:
            self.debug = True

        # Validate and normalize environment_manager
        if self.environment_manager is not None:
            normalized_manager = self.environment_manager.lower()
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
                    f"Invalid environment_manager: '{self.environment_manager}'. "
                    f"Must be one of {VALID_MANAGERS} (case-insensitive), or None."
                )
            self.environment_manager = normalized_manager
