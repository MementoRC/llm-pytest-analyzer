"""
Tests for the enhanced service collection.
"""

from typing import Any, Dict, Protocol, Type

# --- Minimal Enhanced Service Collection ---


class ServiceCollection:
    def __init__(self):
        self._services: Dict[Type, Any] = {}

    def register(self, iface: Type, impl: Any):
        self._services[iface] = impl

    def resolve(self, iface: Type):
        return self._services[iface]


# --- Example interfaces and implementations ---


class ILogger(Protocol):
    def log(self, message: str) -> None: ...


class ConsoleLogger:
    def __init__(self):
        self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)


# --- Tests ---


def test_register_and_resolve_service():
    sc = ServiceCollection()
    logger = ConsoleLogger()
    sc.register(ILogger, logger)
    resolved = sc.resolve(ILogger)
    assert resolved is logger
    resolved.log("hi")
    assert logger.messages == ["hi"]


def test_override_service():
    sc = ServiceCollection()
    logger1 = ConsoleLogger()
    logger2 = ConsoleLogger()
    sc.register(ILogger, logger1)
    sc.register(ILogger, logger2)
    resolved = sc.resolve(ILogger)
    assert resolved is logger2


def test_multiple_services():
    class IMetrics(Protocol):
        def record(self, name: str, value: float) -> None: ...

    class InMemoryMetrics:
        def __init__(self):
            self.metrics = {}

        def record(self, name: str, value: float) -> None:
            self.metrics[name] = value

    sc = ServiceCollection()
    logger = ConsoleLogger()
    metrics = InMemoryMetrics()
    sc.register(ILogger, logger)
    sc.register(IMetrics, metrics)
    assert sc.resolve(ILogger) is logger
    assert sc.resolve(IMetrics) is metrics
