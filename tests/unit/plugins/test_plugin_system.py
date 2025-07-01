from src.pytest_analyzer.core.plugins.manager import PluginManager
from src.pytest_analyzer.core.plugins.protocols import (
    PluginConfigProtocol,
    PluginDependencyProtocol,
    PluginPerformanceProtocol,
    PluginProtocol,
    PluginSandboxProtocol,
)
from src.pytest_analyzer.core.plugins.sandbox import PluginSandbox


class DummyPlugin(
    PluginProtocol,
    PluginConfigProtocol,
    PluginDependencyProtocol,
    PluginSandboxProtocol,
    PluginPerformanceProtocol,
):
    name = "dummy"
    version = "1.0.0"
    description = "Dummy plugin"
    dependencies = []

    def __init__(self):
        self.activated = False
        self.config = {}

    def activate(self):
        self.activated = True

    def deactivate(self):
        self.activated = False

    def get_config(self):
        return self.config

    def set_config(self, config):
        self.config = config

    def check_dependencies(self, available_plugins):
        return True

    def run_in_sandbox(self, func, *args, **kwargs):
        return func(*args, **kwargs)

    def analyze_performance(self):
        return {"dummy_metric": 42}


def test_plugin_lifecycle():
    manager = PluginManager()
    # Register dummy plugin directly for test
    manager.registry.register("dummy", DummyPlugin)
    assert "dummy" in manager.discover_plugins()
    assert manager.load_plugin("dummy")
    assert "dummy" in manager.list_loaded_plugins()
    assert manager.plugins["dummy"].activated
    assert manager.unload_plugin("dummy")
    assert "dummy" not in manager.list_loaded_plugins()


def test_plugin_configuration():
    manager = PluginManager()
    manager.registry.register("dummy", DummyPlugin)
    manager.load_plugin("dummy")
    config = {"foo": "bar"}
    assert manager.configure_plugin("dummy", config)
    assert manager.plugins["dummy"].get_config() == config


def test_plugin_performance_analysis():
    manager = PluginManager()
    manager.registry.register("dummy", DummyPlugin)
    manager.load_plugin("dummy")
    result = manager.analyze_plugin_performance("dummy")
    assert result is not None
    assert "duration" in result
    assert result["result"]["dummy_metric"] == 42


def test_plugin_sandbox():
    sandbox = PluginSandbox()
    plugin = DummyPlugin()
    sandbox.register_plugin(plugin)

    def add(x, y):
        return x + y

    assert sandbox.run_in_sandbox(add, 2, 3) == 5
    sandbox.unregister_plugin(plugin)


def test_plugin_version_compatibility():
    manager = PluginManager()
    manager.registry.register("dummy", DummyPlugin)
    manager.load_plugin("dummy")
    assert manager.check_version_compatibility("dummy", "1.0.5")
    assert not manager.check_version_compatibility("dummy", "2.0.0")
