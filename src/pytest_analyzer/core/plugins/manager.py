import logging
from typing import Any, Dict, List, Optional

from .marketplace import PluginMarketplace
from .performance_analyzer import PluginPerformanceAnalyzer
from .protocols import (
    PluginConfigProtocol,
    PluginDependencyProtocol,
    PluginPerformanceProtocol,
    PluginProtocol,
    PluginSandboxProtocol,
)
from .registry import PluginRegistry
from .sandbox import PluginSandbox

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Main manager for plugin lifecycle, discovery, loading, unloading, dependency resolution,
    configuration, sandboxing, and performance analysis.
    """

    def __init__(
        self,
        registry: Optional[PluginRegistry] = None,
        sandbox: Optional[PluginSandbox] = None,
    ):
        self.registry = registry or PluginRegistry()
        self.sandbox = sandbox or PluginSandbox()
        self.plugins: Dict[str, PluginProtocol] = {}
        self.configs: Dict[str, Dict[str, Any]] = {}
        self.performance_analyzer = PluginPerformanceAnalyzer()
        self.marketplace = PluginMarketplace(self)

    def discover_plugins(self) -> List[str]:
        """Discover available plugins."""
        discovered = self.registry.discover()
        logger.info(f"Discovered plugins: {discovered}")
        return discovered

    def load_plugin(self, plugin_name: str) -> bool:
        """Load a plugin by name, resolving dependencies and configuration."""
        try:
            plugin_cls = self.registry.get_plugin_class(plugin_name)
            plugin: PluginProtocol = plugin_cls()
            # Dependency resolution
            if isinstance(plugin, PluginDependencyProtocol):
                if not plugin.check_dependencies(list(self.plugins.keys())):
                    logger.error(
                        f"Dependencies not satisfied for plugin: {plugin_name}"
                    )
                    return False
            # Configuration
            if isinstance(plugin, PluginConfigProtocol):
                config = self.configs.get(plugin_name, {})
                plugin.set_config(config)
            # Sandboxing
            if isinstance(plugin, PluginSandboxProtocol):
                self.sandbox.register_plugin(plugin)
            plugin.activate()
            self.plugins[plugin_name] = plugin
            logger.info(f"Loaded plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.exception(f"Failed to load plugin {plugin_name}: {e}")
            return False

    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin by name."""
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            logger.warning(f"Plugin not loaded: {plugin_name}")
            return False
        try:
            plugin.deactivate()
            if isinstance(plugin, PluginSandboxProtocol):
                self.sandbox.unregister_plugin(plugin)
            del self.plugins[plugin_name]
            logger.info(f"Unloaded plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.exception(f"Failed to unload plugin {plugin_name}: {e}")
            return False

    def configure_plugin(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """Set configuration for a plugin."""
        plugin = self.plugins.get(plugin_name)
        if not plugin or not isinstance(plugin, PluginConfigProtocol):
            logger.error(f"Plugin {plugin_name} does not support configuration.")
            return False
        try:
            plugin.set_config(config)
            self.configs[plugin_name] = config
            logger.info(f"Configured plugin: {plugin_name}")
            return True
        except Exception as e:
            logger.exception(f"Failed to configure plugin {plugin_name}: {e}")
            return False

    def analyze_plugin_performance(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Analyze the performance impact of a plugin."""
        plugin = self.plugins.get(plugin_name)
        if not plugin or not isinstance(plugin, PluginPerformanceProtocol):
            logger.error(f"Plugin {plugin_name} does not support performance analysis.")
            return None
        try:
            result = self.performance_analyzer.analyze_plugin(plugin)
            logger.info(f"Performance analysis for {plugin_name}: {result}")
            return result
        except Exception as e:
            logger.exception(f"Failed to analyze performance for {plugin_name}: {e}")
            return None

    def check_version_compatibility(self, plugin_name: str, app_version: str) -> bool:
        """Check if a plugin is compatible with the given app version."""
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            logger.error(f"Plugin {plugin_name} not loaded.")
            return False
        plugin_version = getattr(plugin, "version", None)
        # Simple compatibility check: major version match
        if plugin_version and plugin_version.split(".")[0] == app_version.split(".")[0]:
            return True
        logger.warning(
            f"Plugin {plugin_name} version {plugin_version} is not compatible with app version {app_version}"
        )
        return False

    def list_loaded_plugins(self) -> List[str]:
        """List all currently loaded plugins."""
        return list(self.plugins.keys())

    def list_available_plugins(self) -> List[str]:
        """List all available plugins (discovered)."""
        return self.registry.discover()

    def install_plugin_from_marketplace(self, plugin_name: str) -> bool:
        """Install a plugin from the marketplace."""
        return self.marketplace.install_plugin(plugin_name)

    def remove_plugin(self, plugin_name: str) -> bool:
        """Remove a plugin (unload and delete config)."""
        unloaded = self.unload_plugin(plugin_name)
        if unloaded:
            self.configs.pop(plugin_name, None)
        return unloaded
