from src.pytest_analyzer.core.monitoring.dashboard_data import DashboardDataProvider


def test_update_and_get_metric():
    provider = DashboardDataProvider()
    provider.update_metric("tests_passed", 5)
    data = provider.get_data()
    assert data["tests_passed"] == 5


def test_increment_metric():
    provider = DashboardDataProvider()
    provider.update_metric("failures", 2)
    provider.increment_metric("failures")
    assert provider.get_data()["failures"] == 3
    provider.increment_metric("failures", 4)
    assert provider.get_data()["failures"] == 7


def test_set_status():
    provider = DashboardDataProvider()
    provider.set_status("system", "healthy")
    assert provider.get_data()["system"] == "healthy"


def test_subscribe_and_notify():
    provider = DashboardDataProvider()
    received = []

    def callback(data):
        received.append(data.copy())

    provider.subscribe(callback)
    provider.update_metric("foo", 1)
    provider.set_status("bar", "ok")
    # Notifications should be synchronous since they're in the same thread
    assert len(received) == 2
    assert received[0]["foo"] == 1
    assert received[1]["bar"] == "ok"


def test_clear_dashboard_data():
    provider = DashboardDataProvider()
    provider.update_metric("x", 123)
    provider.clear()
    assert provider.get_data() == {}
