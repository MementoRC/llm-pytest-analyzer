"""
Tests for all enhanced DI interfaces and implementations.
"""


# Example interfaces and implementations for the enhanced DI system

from typing import Any, Protocol

# --- Interfaces ---


class ILogger(Protocol):
    def log(self, message: str) -> None: ...


class IMetrics(Protocol):
    def record(self, name: str, value: float) -> None: ...


class ISessionManager(Protocol):
    def start(self) -> None: ...
    def end(self) -> None: ...


class IAnalysisSession(Protocol):
    def analyze(self, data: Any) -> str: ...


# --- Implementations ---


class ConsoleLogger:
    def __init__(self):
        self.messages = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class InMemoryMetrics:
    def __init__(self):
        self.metrics = {}

    def record(self, name: str, value: float) -> None:
        self.metrics[name] = value


class SimpleSessionManager:
    def __init__(self):
        self.started = False
        self.ended = False

    def start(self) -> None:
        self.started = True

    def end(self) -> None:
        self.ended = True


class DummyAnalysisSession:
    def analyze(self, data: Any) -> str:
        return f"analyzed: {data}"


# --- Tests for Implementations ---


def test_console_logger():
    logger = ConsoleLogger()
    logger.log("hello")
    assert logger.messages == ["hello"]


def test_in_memory_metrics():
    metrics = InMemoryMetrics()
    metrics.record("accuracy", 0.95)
    assert metrics.metrics["accuracy"] == 0.95


def test_simple_session_manager():
    mgr = SimpleSessionManager()
    mgr.start()
    assert mgr.started
    mgr.end()
    assert mgr.ended


def test_dummy_analysis_session():
    session = DummyAnalysisSession()
    result = session.analyze("data")
    assert result == "analyzed: data"


# --- Interface Compliance ---


def test_logger_protocol_compliance():
    logger: ILogger = ConsoleLogger()
    logger.log("test")


def test_metrics_protocol_compliance():
    metrics: IMetrics = InMemoryMetrics()
    metrics.record("foo", 1.0)


def test_session_manager_protocol_compliance():
    mgr: ISessionManager = SimpleSessionManager()
    mgr.start()
    mgr.end()


def test_analysis_session_protocol_compliance():
    session: IAnalysisSession = DummyAnalysisSession()
    assert session.analyze("x") == "analyzed: x"
