"""Framework error classes for LLM Task Framework."""


class FrameworkError(Exception):
    """Base exception for framework errors."""

    pass


class TaskNotFoundError(FrameworkError):
    """Raised when a requested task is not found."""

    pass


class TaskRegistrationError(FrameworkError):
    """Raised when task registration fails."""

    pass


class MCPServerError(FrameworkError):
    """Raised for MCP server errors."""

    pass


class TaskExecutionError(FrameworkError):
    """Raised when a task fails during execution."""

    pass


class ConfigurationError(FrameworkError):
    """Raised for configuration-related errors."""

    pass


class PluginDiscoveryError(FrameworkError):
    """Raised when plugin discovery fails."""

    pass
