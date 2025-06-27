import logging
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Pattern, Union

logger = logging.getLogger(__name__)


class Alert:
    """
    Represents an alert triggered by the monitoring system.
    """

    def __init__(
        self,
        name: str,
        message: str,
        severity: str = "critical",
        data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ):
        self.name = name
        self.message = message
        self.severity = severity
        self.data = data or {}
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "message": self.message,
            "severity": self.severity,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class AlertRule:
    """
    Defines a rule for triggering alerts based on thresholds, patterns, or custom conditions.
    """

    def __init__(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        message: str,
        severity: str = "critical",
    ):
        self.name = name
        self.condition = condition
        self.message = message
        self.severity = severity

    def evaluate(self, data: Dict[str, Any]) -> Optional[Alert]:
        if self.condition(data):
            return Alert(
                name=self.name,
                message=self.message,
                severity=self.severity,
                data=data,
            )
        return None


class AlertManager:
    """
    Manages alert rules and dispatches alerts when conditions are met.
    Supports threshold-based, pattern-based, and custom alerting.
    """

    def __init__(self):
        self.rules: List[AlertRule] = []
        self.alerts: List[Alert] = []
        self.subscribers: List[Callable[[Alert], None]] = []
        self._lock = threading.Lock()

    def add_rule(self, rule: AlertRule) -> None:
        with self._lock:
            self.rules.append(rule)
            logger.debug(f"Alert rule added: {rule.name}")

    def add_threshold_rule(
        self,
        name: str,
        key: str,
        threshold: Union[int, float],
        message: Optional[str] = None,
        severity: str = "critical",
        comparison: str = "gte",
    ) -> None:
        """
        Adds a threshold-based alert rule.
        comparison: "gte" (>=), "gt" (>), "lte" (<=), "lt" (<), "eq" (==), "ne" (!=)
        """

        def condition(data: Dict[str, Any]) -> bool:
            value = data.get(key)
            if value is None:
                return False
            if comparison == "gte":
                return value >= threshold
            elif comparison == "gt":
                return value > threshold
            elif comparison == "lte":
                return value <= threshold
            elif comparison == "lt":
                return value < threshold
            elif comparison == "eq":
                return value == threshold
            elif comparison == "ne":
                return value != threshold
            return False

        msg = message or f"{key} {comparison} {threshold}"
        rule = AlertRule(name=name, condition=condition, message=msg, severity=severity)
        self.add_rule(rule)

    def add_pattern_rule(
        self,
        name: str,
        key: str,
        pattern: Union[str, Pattern],
        message: Optional[str] = None,
        severity: str = "critical",
    ) -> None:
        """
        Adds a pattern-based alert rule (e.g., regex match on a log message).
        """
        compiled_pattern = re.compile(pattern) if isinstance(pattern, str) else pattern

        def condition(data: Dict[str, Any]) -> bool:
            value = data.get(key)
            if not isinstance(value, str):
                return False
            return bool(compiled_pattern.search(value))

        msg = message or f"{key} matches pattern {compiled_pattern.pattern}"
        rule = AlertRule(name=name, condition=condition, message=msg, severity=severity)
        self.add_rule(rule)

    def subscribe(self, callback: Callable[[Alert], None]) -> None:
        """
        Subscribe to alert notifications.
        """
        with self._lock:
            self.subscribers.append(callback)

    def notify(self, alert: Alert) -> None:
        """
        Notify all subscribers of an alert.
        """
        for subscriber in self.subscribers:
            try:
                subscriber(alert)
            except Exception as e:
                logger.error(f"Alert subscriber error: {e}")

    def process(self, data: Dict[str, Any]) -> List[Alert]:
        """
        Evaluate all rules against the provided data and trigger alerts as needed.
        """
        triggered_alerts = []
        with self._lock:
            for rule in self.rules:
                alert = rule.evaluate(data)
                if alert:
                    self.alerts.append(alert)
                    triggered_alerts.append(alert)
                    logger.warning(f"ALERT: {alert.message} | Data: {alert.data}")
                    self.notify(alert)
        return triggered_alerts

    def get_alerts(self, since: Optional[float] = None) -> List[Alert]:
        """
        Retrieve all alerts, optionally filtering by timestamp.
        """
        with self._lock:
            if since is not None:
                return [a for a in self.alerts if a.timestamp >= since]
            return list(self.alerts)

    def clear_alerts(self) -> None:
        """
        Clear all stored alerts.
        """
        with self._lock:
            self.alerts.clear()
