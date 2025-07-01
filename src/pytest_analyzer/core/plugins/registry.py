import importlib
import logging
import pkgutil
from typing import Dict, List, Type

from .protocols import PluginProtocol

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Registry for plugin definitions, discovery, and dynamic loading.
    Supports both built-in and external plugins.
    """

    def __init__(self):
        self._plugins: Dict[str, Type[PluginProtocol]] = {}

    def discover(self) -> List[str]:
        """Discover available plugins (built-in and external)."""
        discovered = list(self._plugins.keys())
        # Discover built-in plugins in the plugins directory
        import os

        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        for finder, name, ispkg in pkgutil.iter_modules([plugin_dir]):
            if name not in discovered:
                discovered.append(name)
        return discovered

    def register(self, name: str, plugin_cls: Type[PluginProtocol]) -> None:
        """Register a plugin class."""
        self._plugins[name] = plugin_cls

    def get_plugin_class(self, name: str) -> Type[PluginProtocol]:
        """Get the plugin class by name, loading dynamically if needed."""
        if name in self._plugins:
            return self._plugins[name]
        # Try to import dynamically
        try:
            module = importlib.import_module(f".{name}", __package__)
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type) and issubclass(obj, PluginProtocol):
                    self._plugins[name] = obj
                    return obj
        except Exception as e:
            logger.error(f"Failed to import plugin {name}: {e}")
        raise ImportError(f"Plugin {name} not found.")
