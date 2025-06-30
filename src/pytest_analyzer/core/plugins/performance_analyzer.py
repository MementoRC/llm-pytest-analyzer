import logging
import time
from typing import Any, Dict

from .protocols import PluginPerformanceProtocol

logger = logging.getLogger(__name__)


class PluginPerformanceAnalyzer:
    """
    Analyzes the performance impact of plugins.
    """

    def analyze_plugin(
        self, plugin: PluginPerformanceProtocol, *args, **kwargs
    ) -> Dict[str, Any]:
        """
        Measure execution time and resource usage of a plugin's analyze_performance method.
        """
        try:
            start = time.perf_counter()
            result = plugin.analyze_performance()
            duration = time.perf_counter() - start
            logger.info(
                f"Plugin {getattr(plugin, 'name', str(plugin))} performance: {duration:.4f}s"
            )
            return {
                "plugin": getattr(plugin, "name", str(plugin)),
                "duration": duration,
                "result": result,
            }
        except Exception as e:
            logger.exception(f"Error analyzing plugin performance: {e}")
            return {
                "plugin": getattr(plugin, "name", str(plugin)),
                "error": str(e),
            }
