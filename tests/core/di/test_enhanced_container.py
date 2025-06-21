"""
Integration tests for enhanced DI: injector + legacy container.
"""

from typing import Protocol

from injector import Injector, Module, inject, provider, singleton

# --- Example interfaces and implementations ---


class ILogger(Protocol):
    def log(self, message: str) -> None: ...


class ConsoleLogger:
    def __init__(self):
        self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class IMetrics(Protocol):
    def record(self, name: str, value: float) -> None: ...


class InMemoryMetrics:
    def __init__(self):
        self.metrics = {}

    def record(self, name: str, value: float) -> None:
        self.metrics[name] = value


# --- Legacy container (minimal) ---


class LegacyContainer:
    def __init__(self):
        self._services = {}

    def register_instance(self, iface, impl):
        self._services[iface] = impl

    def resolve(self, iface):
        return self._services[iface]


# --- Integration with injector ---


class AppModule(Module):
    @singleton
    @provider
    def provide_logger(self) -> ILogger:
        return ConsoleLogger()

    @singleton
    @provider
    def provide_metrics(self) -> IMetrics:
        return InMemoryMetrics()


@inject
class Component:
    def __init__(self, logger: ILogger, metrics: IMetrics):
        self.logger = logger
        self.metrics = metrics


def test_injector_and_legacy_container_integration():
    # Set up injector
    injector = Injector([AppModule()])
    logger = injector.get(ILogger)
    metrics = injector.get(IMetrics)

    # Set up legacy container
    legacy = LegacyContainer()
    legacy.register_instance(ILogger, logger)
    legacy.register_instance(IMetrics, metrics)

    # Resolve from legacy container
    logger_legacy = legacy.resolve(ILogger)
    metrics_legacy = legacy.resolve(IMetrics)
    assert isinstance(logger_legacy, ConsoleLogger)
    assert isinstance(metrics_legacy, InMemoryMetrics)

    # Use injector to inject into a component
    comp = injector.get(Component)
    comp.logger.log("msg")
    comp.metrics.record("foo", 42)
    assert comp.logger.messages == ["msg"]
    assert comp.metrics.metrics["foo"] == 42


def test_end_to_end_di():
    injector = Injector([AppModule()])
    comp = injector.get(Component)
    comp.logger.log("end2end")
    comp.metrics.record("bar", 1.23)
    assert comp.logger.messages == ["end2end"]
    assert comp.metrics.metrics["bar"] == 1.23
