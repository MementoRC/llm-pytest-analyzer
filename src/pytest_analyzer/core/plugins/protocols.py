from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class PluginProtocol(Protocol):
    """Base protocol for all plugins."""

    name: str
    version: str
    description: str

    def activate(self) -> None:
        """Activate the plugin."""
        ...

    def deactivate(self) -> None:
        """Deactivate the plugin."""
        ...


@runtime_checkable
class PluginConfigProtocol(Protocol):
    """Protocol for plugin configuration."""

    def get_config(self) -> Dict[str, Any]: ...

    def set_config(self, config: Dict[str, Any]) -> None: ...


@runtime_checkable
class PluginDependencyProtocol(Protocol):
    """Protocol for plugin dependency resolution."""

    dependencies: List[str]

    def check_dependencies(self, available_plugins: List[str]) -> bool: ...


@runtime_checkable
class PluginSandboxProtocol(Protocol):
    """Protocol for plugin sandboxing."""

    def run_in_sandbox(self, func, *args, **kwargs) -> Any: ...


@runtime_checkable
class PluginPerformanceProtocol(Protocol):
    """Protocol for plugin performance analysis."""

    def analyze_performance(self) -> Dict[str, Any]: ...


@runtime_checkable
class PluginMarketplaceProtocol(Protocol):
    """Protocol for plugin marketplace integration."""

    def list_available_plugins(self) -> List[Dict[str, Any]]: ...

    def install_plugin(self, plugin_name: str) -> bool: ...

    def remove_plugin(self, plugin_name: str) -> bool: ...
