import logging
from typing import Any, Callable, Set

from .protocols import PluginSandboxProtocol

logger = logging.getLogger(__name__)


class PluginSandbox:
    """
    Provides sandboxed execution for plugins.
    """

    def __init__(self):
        self._registered_plugins: Set[PluginSandboxProtocol] = set()

    def register_plugin(self, plugin: PluginSandboxProtocol) -> None:
        self._registered_plugins.add(plugin)

    def unregister_plugin(self, plugin: PluginSandboxProtocol) -> None:
        self._registered_plugins.discard(plugin)

    def run_in_sandbox(self, func: Callable, *args, **kwargs) -> Any:
        """
        Run a function in a restricted environment.
        """
        try:
            # In a real implementation, use restricted globals/locals, resource limits, etc.
            # Here, we just log and call the function.
            logger.debug(f"Running {func} in plugin sandbox.")
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Error in sandboxed plugin execution: {e}")
            raise
