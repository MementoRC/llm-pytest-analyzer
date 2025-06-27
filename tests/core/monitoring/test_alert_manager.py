from src.pytest_analyzer.core.monitoring.alert_manager import (
    AlertManager,
    AlertRule,
)


def test_threshold_alert_triggered():
    manager = AlertManager()
    manager.add_threshold_rule(
        name="High Error Rate",
        key="error_rate",
        threshold=0.5,
        comparison="gte",
        message="Error rate too high!",
        severity="critical",
    )
    data = {"error_rate": 0.7}
    alerts = manager.process(data)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.name == "High Error Rate"
    assert alert.severity == "critical"
    assert "Error rate too high" in alert.message
    assert alert.data["error_rate"] == 0.7


def test_pattern_alert_triggered():
    manager = AlertManager()
    manager.add_pattern_rule(
        name="Sensitive Error",
        key="log_message",
        pattern="CRITICAL SECURITY",
        message="Security issue detected",
        severity="critical",
    )
    data = {"log_message": "CRITICAL SECURITY: Unauthorized access"}
    alerts = manager.process(data)
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.name == "Sensitive Error"
    assert "Security issue detected" in alert.message


def test_custom_rule_alert():
    def custom_condition(data):
        return data.get("failures", 0) > 10

    rule = AlertRule(
        name="Too Many Failures",
        condition=custom_condition,
        message="More than 10 failures detected",
        severity="warning",
    )
    manager = AlertManager()
    manager.add_rule(rule)
    data = {"failures": 12}
    alerts = manager.process(data)
    assert len(alerts) == 1
    assert alerts[0].name == "Too Many Failures"
    assert alerts[0].severity == "warning"


def test_alert_subscription(monkeypatch):
    manager = AlertManager()
    received = []

    def subscriber(alert):
        received.append(alert)

    manager.subscribe(subscriber)
    manager.add_threshold_rule(
        name="High CPU",
        key="cpu",
        threshold=90,
        comparison="gte",
        message="CPU usage high",
        severity="critical",
    )
    data = {"cpu": 95}
    alerts = manager.process(data)
    assert len(alerts) == 1
    assert received[0].name == "High CPU"


def test_get_and_clear_alerts():
    manager = AlertManager()
    manager.add_threshold_rule(
        name="Memory Alert",
        key="memory",
        threshold=80,
        comparison="gte",
        message="Memory usage high",
        severity="critical",
    )
    data = {"memory": 85}
    alerts = manager.process(data)
    assert len(alerts) == 1
    all_alerts = manager.get_alerts()
    assert len(all_alerts) == 1
    manager.clear_alerts()
    assert manager.get_alerts() == []
