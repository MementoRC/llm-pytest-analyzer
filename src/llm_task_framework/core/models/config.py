"""TaskConfig dataclass for LLM Task Framework."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class LLMProviderConfig:
    """
    Configuration for the LLM provider.
    """

    provider: str
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    model: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPServerConfig:
    """
    Configuration for the MCP server.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    transport: str = "stdio"  # or "http"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EnvironmentConfig:
    """
    Configuration for the execution environment.
    """

    python_version: Optional[str] = None
    requirements: Optional[str] = None
    env_vars: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskConfig:
    """
    Configuration for a task execution.
    """

    name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    version: Optional[str] = None
    llm: Optional[LLMProviderConfig] = None
    mcp_server: Optional[MCPServerConfig] = None
    environment: Optional[EnvironmentConfig] = None
    extra: Dict[str, Any] = field(default_factory=dict)
