"""
Example usage of the enhanced DI system with documentation.
"""

from typing import Protocol

from injector import Injector, Module, inject, provider, singleton

# --- Interfaces ---


class ILogger(Protocol):
    def log(self, message: str) -> None: ...


class IMetrics(Protocol):
    def record(self, name: str, value: float) -> None: ...


# --- Implementations ---


class ConsoleLogger:
    def log(self, message: str) -> None:
        print(f"[LOG] {message}")


class InMemoryMetrics:
    def __init__(self):
        self.metrics = {}

    def record(self, name: str, value: float) -> None:
        self.metrics[name] = value
        print(f"[METRIC] {name} = {value}")


# --- DI Module ---


class AppModule(Module):
    @singleton
    @provider
    def provide_logger(self) -> ILogger:
        return ConsoleLogger()

    @singleton
    @provider
    def provide_metrics(self) -> IMetrics:
        return InMemoryMetrics()


# --- Real component using DI ---


@inject
class MyService:
    def __init__(self, logger: ILogger, metrics: IMetrics):
        self.logger = logger
        self.metrics = metrics

    def do_work(self):
        self.logger.log("Doing work")
        self.metrics.record("work_done", 1.0)


# --- Example usage ---


def main():
    injector = Injector([AppModule()])
    service = injector.get(MyService)
    service.do_work()


if __name__ == "__main__":
    main()

"""
Documentation: Enhanced Dependency Injection Approach
====================================================

- Interfaces (ILogger, IMetrics, etc) are defined as Python Protocols.
- Implementations (ConsoleLogger, InMemoryMetrics, etc) provide concrete logic.
- The injector library is used to wire dependencies via modules and providers.
- Components (like MyService) declare dependencies in their constructor and are injected automatically.
- The DI system supports both singleton and transient lifetimes.
- Legacy containers can be integrated by registering injector-provided instances.
- This approach enables testability, modularity, and clear separation of concerns.

To use:
    1. Define your interfaces as Protocols.
    2. Implement concrete classes.
    3. Create an injector.Module subclass with @provider methods.
    4. Use @inject on your components.
    5. Use Injector([YourModule()]) to resolve components.

See tests/core/di/ for comprehensive tests and integration examples.
"""
