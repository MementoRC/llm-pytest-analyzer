"""
Tests for advanced Dependency Injection Container features.

This module tests the more advanced features of the DI container, including:
- Scoped registrations
- Container hierarchies
- Decorator-based registration
- Bulk registration
"""

from typing import List, Protocol

import pytest

from src.pytest_analyzer.core.di import (
    Container,
    RegistrationMode,
    factory,
    register,
    singleton,
    transient,
)
from src.pytest_analyzer.core.errors import (
    DependencyResolutionError,
)


# Test classes and protocols for container testing
class IService(Protocol):
    """Test protocol for a service interface."""

    def execute(self) -> str:
        """Execute the service."""
        ...


class Service:
    """Test implementation of a service."""

    def execute(self) -> str:
        """Execute the service."""
        return "Service executed"


class ICalculator(Protocol):
    """Test protocol for a calculator interface."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        ...


class Calculator:
    """Test implementation of a calculator."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b


class ILogger(Protocol):
    """Test protocol for a logger interface."""

    def log(self, message: str) -> None:
        """Log a message."""
        ...


class Logger:
    """Test implementation of a logger."""

    def __init__(self):
        self.logs: List[str] = []

    def log(self, message: str) -> None:
        """Log a message."""
        self.logs.append(message)


class ISession(Protocol):
    """Test protocol for a session interface."""

    def get_id(self) -> str:
        """Get the session ID."""
        ...


class Session:
    """Test implementation of a session."""

    def __init__(self):
        """Initialize with a unique ID."""
        import uuid

        self._id = str(uuid.uuid4())

    def get_id(self) -> str:
        """Get the session ID."""
        return self._id


class ServiceWithDependencies:
    """Test service with multiple dependencies."""

    def __init__(self, calculator: ICalculator, logger: ILogger, session: ISession):
        """Initialize with dependencies."""
        self.calculator = calculator
        self.logger = logger
        self.session = session

    def execute(self) -> str:
        """Execute with dependencies."""
        result = self.calculator.add(1, 2)
        self.logger.log(f"Session {self.session.get_id()}: calculated {result}")
        return f"Result: {result}"


class TestAdvancedContainer:
    """Tests for advanced DI Container features."""

    def test_scoped_registration(self):
        """Test scoped registrations."""
        container = Container()
        container.register_scoped(ISession, Session)

        # Create a scope
        container.begin_scope()

        # Resolve the session from the scope
        session1 = container.resolve(ISession)
        session2 = container.resolve(ISession)

        # Same instance within the same scope
        assert session1 is session2
        assert session1.get_id() == session2.get_id()

        # End the scope
        container.end_scope()

        # Start a new scope
        container.begin_scope()

        # Resolve the session from the new scope
        session3 = container.resolve(ISession)

        # Different instance in a different scope
        assert session1 is not session3
        assert session1.get_id() != session3.get_id()

        # Clean up
        container.end_scope()

    def test_scoped_dependencies(self):
        """Test resolving scoped dependencies in a larger object graph."""
        container = Container()
        container.register(ICalculator, Calculator)
        container.register(ILogger, Logger)
        container.register_scoped(ISession, Session)
        container.register_transient(IService, ServiceWithDependencies)

        # Create a scope
        container.begin_scope()

        # Resolve the service
        service1 = container.resolve(IService)
        service2 = container.resolve(IService)

        # Different service instances but same session
        assert service1 is not service2
        assert service1.session is service2.session

        # End the scope
        container.end_scope()

    def test_scoped_error_without_scope(self):
        """Test error when resolving scoped dependency without an active scope."""
        container = Container()
        container.register_scoped(ISession, Session)

        # No active scope, should raise error
        with pytest.raises(DependencyResolutionError) as exc_info:
            container.resolve(ISession)

        assert "without an active scope" in str(exc_info.value)

    def test_parent_child_containers(self):
        """Test hierarchical container resolution."""
        # Parent container with basic services
        parent = Container()
        parent.register(ICalculator, Calculator)
        parent.register(ILogger, Logger)

        # Child container with specialized services
        child = Container(parent=parent)
        child.register(IService, Service)

        # Child should resolve its own registrations
        service = child.resolve(IService)
        assert isinstance(service, Service)

        # Child should also resolve parent's registrations
        calculator = child.resolve(ICalculator)
        assert isinstance(calculator, Calculator)
        logger = child.resolve(ILogger)
        assert isinstance(logger, Logger)

        # Parent should not resolve child's registrations
        with pytest.raises(DependencyResolutionError):
            parent.resolve(IService)

    def test_register_decorators(self):
        """Test decorator-based registration."""
        container = Container()

        # Test class decorator with interface
        @register(container, IService)
        class ServiceImpl(Service):
            pass

        # Test class decorator without interface
        @register(container)
        class StandaloneService:
            def execute(self) -> str:
                return "Standalone executed"

        # Test singleton decorator
        @singleton(container, ICalculator)
        class CalculatorImpl(Calculator):
            pass

        # Test transient decorator
        @transient(container, ILogger)
        class LoggerImpl(Logger):
            pass

        # Verify registrations
        resolved_service = container.resolve(IService)
        assert isinstance(resolved_service, ServiceImpl)

        resolved_standalone = container.resolve(StandaloneService)
        assert isinstance(resolved_standalone, StandaloneService)

        calc1 = container.resolve(ICalculator)
        calc2 = container.resolve(ICalculator)
        assert calc1 is calc2  # Same instance (singleton)

        logger1 = container.resolve(ILogger)
        logger2 = container.resolve(ILogger)
        assert logger1 is not logger2  # Different instances (transient)

    def test_factory_decorator(self):
        """Test factory decorator."""
        container = Container()

        # Test factory function decorator
        @factory(container, ISession)
        def create_session() -> ISession:
            return Session()

        # Verify factory registration
        session = container.resolve(ISession)
        assert isinstance(session, Session)

    def test_inject_decorator(self):
        """Test the inject decorator for function injection."""
        # Modified to use inject with a provided container
        from src.pytest_analyzer.core.di.decorators import inject

        # Create container
        container = Container()
        container.register(ILogger, Logger)
        container.register(ICalculator, Calculator)

        # Test injecting function parameters
        @inject(container)
        def process_data(logger: ILogger, calculator: ICalculator, optional_param: str = "default"):
            logger.log(f"Processing with optional param: {optional_param}")
            return calculator.add(10, 20)

        # Call without arguments - should inject logger and calculator
        result = process_data()
        assert result == 30

        # Call with optional param - should still inject the required deps
        result = process_data(optional_param="custom")
        assert result == 30

        # Call with explicit arguments - should use those instead of injecting
        my_logger = Logger()
        my_calculator = Calculator()
        result = process_data(logger=my_logger, calculator=my_calculator)
        assert result == 30
        assert "Processing with optional param: default" in my_logger.logs

    def test_inject_decorator_on_method(self):
        """Test the inject decorator on method."""
        # Modified to use inject with a provided container
        from src.pytest_analyzer.core.di.decorators import inject

        # Create container
        container = Container()
        container.register(ILogger, Logger)

        class DataProcessor:
            @inject(container)
            def process(self, logger: ILogger, data: str):
                logger.log(f"Processing: {data}")
                return f"Processed: {data}"

        # Create processor
        processor = DataProcessor()

        # Call method with just data, logger should be injected
        result = processor.process(data="test data")
        assert result == "Processed: test data"

        # Verify the log was created in the injected logger
        logger = container.resolve(ILogger)
        assert "Processing: test data" in logger.logs

    def test_bulk_registration(self):
        """Test registering multiple dependencies at once."""
        container = Container()

        # Register multiple types at once
        container.register_many({ICalculator: Calculator, ILogger: Logger, IService: Service})

        # Verify all registrations
        assert isinstance(container.resolve(ICalculator), Calculator)
        assert isinstance(container.resolve(ILogger), Logger)
        assert isinstance(container.resolve(IService), Service)

        # Register with different modes
        container.register_many({ISession: Session}, mode=RegistrationMode.TRANSIENT)

        # Verify transient registration
        session1 = container.resolve(ISession)
        session2 = container.resolve(ISession)
        assert session1 is not session2

    def test_register_instance(self):
        """Test registering existing instances."""
        container = Container()

        # Create instances
        calculator = Calculator()
        logger = Logger()

        # Register instances
        container.register_instance(ICalculator, calculator)
        container.register_instance(ILogger, logger)

        # Verify the exact same instances are resolved
        assert container.resolve(ICalculator) is calculator
        assert container.resolve(ILogger) is logger
