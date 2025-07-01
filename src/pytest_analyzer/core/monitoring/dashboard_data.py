import logging
import threading
import time
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class DashboardDataProvider:
    """
    Aggregates and provides real-time monitoring data for dashboard consumption.
    Supports metrics, status, and custom data sources.
    """

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._last_update: float = time.time()

    def update_metric(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._last_update = time.time()
            logger.debug(f"Dashboard metric updated: {key}={value}")
            self._notify_subscribers()

    def increment_metric(self, key: str, amount: int = 1) -> None:
        with self._lock:
            current = self._data.get(key, 0)
            if not isinstance(current, (int, float)):
                current = 0
            self._data[key] = current + amount
            self._last_update = time.time()
            logger.debug(f"Dashboard metric incremented: {key}={self._data[key]}")
            self._notify_subscribers()

    def set_status(self, key: str, status: str) -> None:
        with self._lock:
            self._data[key] = status
            self._last_update = time.time()
            logger.debug(f"Dashboard status set: {key}={status}")
            self._notify_subscribers()

    def get_data(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def get_last_update(self) -> float:
        with self._lock:
            return self._last_update

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Subscribe to real-time dashboard data updates.
        """
        with self._lock:
            self._subscribers.append(callback)

    def _notify_subscribers(self) -> None:
        # Get data without acquiring lock again to avoid recursion
        data_copy = dict(self._data)
        for callback in self._subscribers:
            try:
                callback(data_copy)
            except Exception as e:
                logger.error(f"Dashboard subscriber error: {e}")

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._last_update = time.time()
            logger.debug("Dashboard data cleared")
            self._notify_subscribers()
